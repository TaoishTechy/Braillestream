#!/usr/bin/env python3
"""
rgpuf_core.py
==============

Reusable core for the Retro Game Physics Unified Framework.

Contains:
- compact retro-physics laws
- resource thermodynamics
- topology and cell-world logic
- Freescape-style zone/cuboid physics
- adaptive agents
- law-stack metrics
- HDC semantic drift engine
- DLASc dynamic law compiler
- audit/optimization primitives

This file is importable and should not run full demos by default.
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

TAU = math.tau
BASE_MODES = ["lander", "asteroids", "pressure", "freescape", "colony", "semantic"]

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Constants
# ═══════════════════════════════════════════════════════════════════════════════

VERIFIED_WEIGHT = {"historical": 1.0, "equivalent": 0.7, "speculative": 0.3}
SECTOR_DIRS = [(0, -1, "n"), (1, 0, "e"), (0, 1, "s"), (-1, 0, "w")]
WALL_RIGHT = ["e", "s", "w", "n"]
WALL_LEFT = ["w", "n", "e", "s"]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Math Primitives
# ═══════════════════════════════════════════════════════════════════════════════

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def wrap(v: float, size: float) -> float:
    """Toroidal boundary: Asteroids / 3-Demon / Elite / Colony wrap."""
    return v % size


@dataclass
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: Vec2) -> Vec2:
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: Vec2) -> Vec2:
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, s: float) -> Vec2:
        return Vec2(self.x * s, self.y * s)

    def dot(self, o: Vec2) -> float:
        return self.x * o.x + self.y * o.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def distance_to(self, o: Vec2) -> float:
        return (self - o).length()

    def rotate(self, rad: float) -> Vec2:
        c, s = math.cos(rad), math.sin(rad)
        return Vec2(self.x * c - self.y * s, self.x * s + self.y * c)

    def normalized(self) -> Vec2:
        m = self.length()
        return Vec2(self.x / m, self.y / m) if m > 1e-9 else Vec2()

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def quantized(self, scale: float = 1.0) -> tuple[int, int]:
        return (int(self.x / scale), int(self.y / scale))


@dataclass
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, o: Vec3) -> Vec3:
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: Vec3) -> Vec3:
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s: float) -> Vec3:
        return Vec3(self.x * s, self.y * s, self.z * s)

    def dot(self, o: Vec3) -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def distance_to(self, o: Vec3) -> float:
        return (self - o).length()

    def rotate_y(self, rad: float) -> Vec3:
        c, s = math.cos(rad), math.sin(rad)
        return Vec3(self.x * c + self.z * s, self.y, -self.x * s + self.z * c)

    def normalized(self) -> Vec3:
        m = self.length()
        return Vec3(self.x / m, self.y / m, self.z / m) if m > 1e-9 else Vec3()

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def quantized(self, scale: float = 1.0) -> tuple[int, int, int]:
        return (int(self.x / scale), int(self.y / scale), int(self.z / scale))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Core Dataclasses
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class Body:
    """Rigid body with 2D position, velocity, quantized heading, and extended state."""
    pos: Vec2 = field(default_factory=Vec2)
    vel: Vec2 = field(default_factory=Vec2)
    mass: float = 1.0
    radius: float = 1.0
    heading_byte: int = 64
    height: float = 0.0
    mode: str = "ground"
    zone_id: int = 0
    state: str = "active"

    # v4: event counters for measured agency
    last_pos: Vec2 = field(default_factory=Vec2)
    collision_count: int = 0
    wrap_count: int = 0
    teleport_count: int = 0

    @property
    def heading_rad(self) -> float:
        return (self.heading_byte / 256.0) * TAU

    @property
    def forward(self) -> Vec2:
        a = self.heading_rad
        return Vec2(math.cos(a), math.sin(a))

    def rotate_quantized(self, ticks: int) -> None:
        self.heading_byte = (self.heading_byte + ticks) % 256


@dataclass
class Body3:
    """3D body for Freescape / Colony spatial modes."""
    pos: Vec3 = field(default_factory=Vec3)
    vel: Vec3 = field(default_factory=Vec3)
    heading_byte: int = 0
    zone_id: int = 0
    state: str = "active"

    last_pos: Vec3 = field(default_factory=Vec3)
    collision_count: int = 0
    wrap_count: int = 0
    teleport_count: int = 0

    @property
    def heading_rad(self) -> float:
        return (self.heading_byte / 256.0) * TAU

    def rotate_quantized(self, ticks: int) -> None:
        self.heading_byte = (self.heading_byte + ticks) % 256


@dataclass
class ResourceReservoir:
    """Universal RGPUF resource law -- Eq. 2:
        dR/dt = source(t) - sink(t) - leak * R + noise
    """
    value: float
    capacity: float
    leak: float = 0.0
    critical: float | None = None

    def step(self, dt: float, source: float = 0.0,
             sink: float = 0.0, noise: float = 0.0) -> None:
        self.value += (source - sink - self.leak * self.value + noise) * dt
        self.value = clamp(self.value, 0.0, self.capacity)

    @property
    def criticality(self) -> float:
        if self.critical is None or self.critical <= 0:
            return self.value / max(self.capacity, 1e-9)
        return self.value / self.critical

    def normalized(self) -> float:
        return self.value / max(self.capacity, 1e-9)

    def failure_margin(self) -> float:
        if self.critical is None:
            return 1.0 - self.normalized()
        return (self.value - self.critical) / max(self.critical, 1e-9)

    def is_critical(self) -> bool:
        if self.critical is None:
            return self.value < self.capacity * 0.1
        return self.value < self.critical


@dataclass
class Zone:
    """Per-zone physical laws -- Driller / Freescape style."""
    id: int
    gravity: float = 1.0
    friction: float = 0.1
    light_radius: float = 999.0
    time_scale: float = 1.0
    pressure: float = 25.0
    neighbors: list[int] = field(default_factory=list)


@dataclass
class Cuboid:
    """Axis-aligned bounding box -- Freespace / Driller constructive geometry."""
    mn: Vec3 = field(default_factory=Vec3)
    mx: Vec3 = field(default_factory=Vec3)
    solid: bool = True


def inside_cuboid(p: Vec3, c: Cuboid) -> bool:
    return (c.mn.x <= p.x <= c.mx.x and
            c.mn.y <= p.y <= c.mx.y and
            c.mn.z <= p.z <= c.mx.z)


def cuboid_collide(p: Vec3, vel: Vec3, c: Cuboid) -> tuple[bool, Vec3]:
    if not inside_cuboid(p, c) or not c.solid:
        return False, vel
    pen_x = min(p.x - c.mn.x, c.mx.x - p.x)
    pen_y = min(p.y - c.mn.y, c.mx.y - p.y)
    pen_z = min(p.z - c.mn.z, c.mx.z - p.z)
    if pen_x <= pen_y and pen_x <= pen_z:
        vel.x *= -0.3
        p.x = (c.mn.x - 0.01) if (p.x - c.mn.x) < (c.mx.x - p.x) else (c.mx.x + 0.01)
    elif pen_y <= pen_z:
        vel.y *= -0.3
        p.y = (c.mn.y - 0.01) if (p.y - c.mn.y) < (c.mx.y - p.y) else (c.mx.y + 0.01)
    else:
        vel.z *= -0.3
        p.z = (c.mn.z - 0.01) if (p.z - c.mn.z) < (c.mx.z - p.z) else (c.mx.z + 0.01)
    return True, vel


@dataclass
class Cell:
    """Colony / 3-Demon cell: compressed spatial law."""
    walls: dict[str, bool] = field(default_factory=lambda: {
        "n": True, "s": True, "e": True, "w": True, "u": False, "d": False,
    })
    object_id: int = 0
    furniture: bool = False
    teleport_to: tuple[int, int] | None = None
    energy_station: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Law Registry v4
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class LawTerm:
    """Law descriptor. No `active` flag -- LawStack handles runtime state."""
    name: str
    family: str
    cost: float
    verified: str  # "historical" | "equivalent" | "speculative"
    preconditions: tuple[str, ...] = ()
    effects: tuple[str, ...] = ()
    trust: float = 1.0
    token_cost: int = 2  # Gödel tokens needed for repair trial


@dataclass
class LawStack:
    """Runtime law stack -- the v4 keystone.
    Global registry describes *available* laws.
    LawStack describes *actually executed* laws.
    This prevents the v3 bug where global active flags inflated every mode.
    """
    names: list[str] = field(default_factory=list)

    def has(self, name: str) -> bool:
        return name in self.names

    def add(self, name: str) -> None:
        if name not in self.names:
            self.names.append(name)

    def remove(self, name: str) -> None:
        if name in self.names:
            self.names.remove(name)

    def cost(self, registry: dict[str, LawTerm]) -> float:
        return sum(registry[n].cost for n in self.names if n in registry)

    def falsifiability(self, registry: dict[str, LawTerm]) -> float:
        if not self.names:
            return 0.0
        weights = {"historical": 1.0, "equivalent": 0.7, "speculative": 0.3}
        total = sum(
            weights.get(registry[n].verified, 0.3) * registry[n].trust
            for n in self.names if n in registry
        )
        return total / len(self.names)

    def count(self) -> int:
        return len(self.names)


LAW_REGISTRY: dict[str, LawTerm] = {
    # Motion family
    "thrust_gravity_drag": LawTerm(
        "thrust_gravity_drag", "motion", 1.0, "equivalent",
        effects=("motion", "control")
    ),
    "central_gravity_well": LawTerm(
        "central_gravity_well", "motion", 1.2, "historical",
        effects=("orbital_motion",)
    ),
    "quantized_rotation": LawTerm(
        "quantized_rotation", "motion", 0.5, "historical",
        effects=("heading_discrete",)
    ),
    # Topology family
    "toroidal_wrap": LawTerm(
        "toroidal_wrap", "topology", 0.5, "historical",
        preconditions=("wrap_enabled",),
        effects=("boundary_continuity",)
    ),
    "teleport_transform": LawTerm(
        "teleport_transform", "topology", 1.0, "historical",
        preconditions=("teleport_trigger",),
        effects=("state_continuity",)
    ),
    # Resource family
    "resource_thermodynamics": LawTerm(
        "resource_thermodynamics", "resource", 1.0, "equivalent",
        effects=("fuel_drain", "heat_buildup")
    ),
    "graph_pressure_diffusion": LawTerm(
        "graph_pressure_diffusion", "resource", 1.5, "equivalent",
        preconditions=("zone_graph",),
        effects=("pressure_equilibrium",)
    ),
    "hysteresis_failure": LawTerm(
        "hysteresis_failure", "failure", 1.5, "equivalent",
        preconditions=("critical_resource",),
        effects=("failure_memory",)
    ),
    # Spatial family
    "cuboid_collision": LawTerm(
        "cuboid_collision", "spatial", 1.5, "historical",
        preconditions=("cuboid_world",),
        effects=("spatial_constraint",)
    ),
    "zone_gravity_friction": LawTerm(
        "zone_gravity_friction", "spatial", 1.0, "historical",
        preconditions=("zone_system",),
        effects=("spatial_constraint",)
    ),
    "hydraulic_height": LawTerm(
        "hydraulic_height", "spatial", 1.2, "equivalent",
        preconditions=("zone_system",),
        effects=("agency_increase",)
    ),
    # Colony family
    "cell_occupancy": LawTerm(
        "cell_occupancy", "colony", 1.0, "historical",
        preconditions=("cell_grid",),
        effects=("spatial_constraint",)
    ),
    "bresenham_los": LawTerm(
        "bresenham_los", "colony", 0.8, "historical",
        preconditions=("cell_grid",),
        effects=("prediction_repair",)
    ),
    "toroidal_surface": LawTerm(
        "toroidal_surface", "colony", 0.5, "historical",
        preconditions=("torus_world",),
        effects=("state_continuity",)
    ),
    "power_suit_energy": LawTerm(
        "power_suit_energy", "colony", 1.0, "equivalent",
        effects=("energy_drain",)
    ),
    # Adaptive agent family
    "wall_following_agent": LawTerm(
        "wall_following_agent", "agent", 1.0, "equivalent",
        preconditions=("cell_grid", "blocked_actions_high"),
        effects=("coverage_increase", "agency_increase"),
        token_cost=2
    ),
    "pid_controller": LawTerm(
        "pid_controller", "agent", 1.2, "equivalent",
        preconditions=("continuous_motion", "landing_target"),
        effects=("agency_increase",),
        token_cost=2
    ),
    "risk_policy": LawTerm(
        "risk_policy", "agent", 0.8, "speculative",
        preconditions=("pressure_reservoir",),
        effects=("stabilization",),
        token_cost=1
    ),
    # Semantic family
    "playable_reality": LawTerm(
        "playable_reality", "semantic", 2.0, "speculative",
        effects=("metric_headline",)
    ),
    "minimum_law_efficiency": LawTerm(
        "minimum_law_efficiency", "semantic", 2.0, "speculative",
        effects=("metric_mle",)
    ),
    "compression_ratio": LawTerm(
        "compression_ratio", "semantic", 1.5, "speculative",
        effects=("metric_cr",)
    ),
    "semantic_entropy": LawTerm(
        "semantic_entropy", "semantic", 2.0, "speculative",
        effects=("metric_se",)
    ),
}


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Agent Stats, SimConfig, SimState, Telemetry
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class AgentStats:
    """Separates action success from goal success."""
    attempted: int = 0
    moved: int = 0
    useful: int = 0
    blocked: int = 0
    collisions: int = 0
    teleports: int = 0
    failures: int = 0

    @property
    def action_agency(self) -> float:
        return self.moved / max(self.attempted, 1)

    @property
    def goal_agency(self) -> float:
        return self.useful / max(self.attempted, 1)


@dataclass
class SimConfig:
    dt: float = 0.12
    adaptive: bool = False
    agent_policy: str = "naive"
    integrator: str = "euler"
    wall_density: float = 0.45
    teleport_probability: float = 0.04
    pressure_source: float = 1.15
    drill_power: float = 8.0
    hdc_dim: int = 1024
    anomaly_threshold: float = 0.25
    law_cost_scale: str = "normalized"
    stress: bool = False
    max_steps: int = 240


@dataclass
class Telemetry:
    """v4 telemetry packet -- richer than v3 Metrics."""
    step: int
    mode: str
    seed: int
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    speed: float = 0.0

    fuel: float = 0.0
    heat: float = 0.0
    pressure: float = 0.0
    suit: float = 0.0
    shield: float = 0.0

    criticality: float = 0.0
    pr: float = 0.0
    pr_norm: float = 0.0
    mle: float = 0.0
    law_cost: float = 0.0
    law_count: int = 0
    falsifiability: float = 0.0
    semantic_entropy: float = 0.0
    prediction_error: float = 0.0
    action_agency: float = 0.0
    goal_agency: float = 0.0
    coverage: float = 0.0
    state_density: float = 0.0
    ambiguity: float = 0.0
    compression_gain: float = 0.0

    godel_tokens: int = 0
    semantic_drift: float = 0.0
    delta_ep_min: float = 0.0

    active_laws: str = ""
    events: str = ""
    failure_state: str = "active"
    zone_id: int = 0
    heading_byte: int = 0
    cell_pos: str = ""

    def csv_row(self) -> dict[str, Any]:
        return {
            "step": self.step, "mode": self.mode, "seed": self.seed,
            "x": round(self.x, 2), "y": round(self.y, 2), "z": round(self.z, 2),
            "speed": round(self.speed, 3),
            "fuel": round(self.fuel, 2), "heat": round(self.heat, 2),
            "pressure": round(self.pressure, 2), "suit": round(self.suit, 2),
            "shield": round(self.shield, 2),
            "criticality": round(self.criticality, 4),
            "pr": round(self.pr, 4), "pr_norm": round(self.pr_norm, 4),
            "mle": round(self.mle, 4),
            "law_cost": round(self.law_cost, 2), "law_count": self.law_count,
            "falsifiability": round(self.falsifiability, 4),
            "semantic_entropy": round(self.semantic_entropy, 4),
            "prediction_error": round(self.prediction_error, 4),
            "action_agency": round(self.action_agency, 4),
            "goal_agency": round(self.goal_agency, 4),
            "coverage": round(self.coverage, 4),
            "state_density": round(self.state_density, 4),
            "ambiguity": round(self.ambiguity, 4),
            "compression_gain": round(self.compression_gain, 4),
            "godel_tokens": self.godel_tokens,
            "semantic_drift": round(self.semantic_drift, 4),
            "delta_ep_min": round(self.delta_ep_min, 4),
            "active_laws": self.active_laws,
            "failure_state": self.failure_state,
            "zone_id": self.zone_id,
            "cell_pos": self.cell_pos,
        }


@dataclass
class SimState:
    """Unified simulation state container."""
    mode: str
    seed: int
    step: int
    config: SimConfig
    law_stack: LawStack
    agent_stats: AgentStats
    hdc: HDCEngine | None
    history: list[Telemetry] = field(default_factory=list)

    body: Body | None = None
    body3: Body3 | None = None
    resources: dict[str, ResourceReservoir] = field(default_factory=dict)
    zones: list[Zone] = field(default_factory=list)
    cuboids: list[Cuboid] = field(default_factory=list)
    grid: dict[tuple[int, int], Cell] = field(default_factory=dict)
    visited_cells: set[tuple[int, int]] = field(default_factory=set)
    signatures: set[tuple] = field(default_factory=set)

    extra: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Physics Laws
# ═══════════════════════════════════════════════════════════════════════════════


def arcade_motion_step(
    body: Body, dt: float, thrust: float,
    gravity: Vec2, drag: float,
    world: Vec2, wrap_edges: bool,
) -> None:
    """Unified arcade motion -- Eq. 1:
        F = T * forward + m * g - drag * v + external
    """
    body.last_pos = Vec2(body.pos.x, body.pos.y)
    force = body.forward * thrust + gravity * body.mass - body.vel * drag
    acc = force * (1.0 / body.mass)
    body.vel = body.vel + acc * dt
    body.pos = body.pos + body.vel * dt

    if wrap_edges:
        old_x, old_y = body.pos.x, body.pos.y
        body.pos.x = wrap(body.pos.x, world.x)
        body.pos.y = wrap(body.pos.y, world.y)
        if body.pos.x != old_x or body.pos.y != old_y:
            body.wrap_count += 1
    else:
        if body.pos.x < 0 or body.pos.x > world.x:
            body.vel.x *= -0.85
            body.collision_count += 1
            body.pos.x = clamp(body.pos.x, 0, world.x)
        if body.pos.y < 0:
            body.vel.y *= -0.30
            body.collision_count += 1
            body.pos.y = 0
        if body.pos.y > world.y:
            body.vel.y *= -0.85
            body.collision_count += 1
            body.pos.y = world.y


def motion_step_3d(
    body: Body3, dt: float, gravity: float,
    friction: float, world: Vec3,
    wrap_edges: bool = False,
) -> None:
    """3D motion with per-zone gravity and friction."""
    body.last_pos = Vec3(body.pos.x, body.pos.y, body.pos.z)
    body.vel.y -= gravity * dt
    body.vel.x *= (1.0 - friction)
    body.vel.z *= (1.0 - friction)
    body.pos = body.pos + body.vel * dt
    if wrap_edges:
        old_x, old_z = body.pos.x, body.pos.z
        body.pos.x = wrap(body.pos.x, world.x)
        body.pos.z = wrap(body.pos.z, world.z)
        if body.pos.x != old_x or body.pos.z != old_z:
            body.wrap_count += 1
    else:
        body.pos.x = clamp(body.pos.x, 0, world.x)
        body.pos.z = clamp(body.pos.z, 0, world.z)
        if body.pos.y < 0:
            body.pos.y = 0
            body.vel.y *= -0.3


def central_gravity_well(
    body: Body, attractor: Vec2, gm: float, softening: float = 25.0
) -> Vec2:
    """Spacewar!-style central force with softening."""
    delta = attractor - body.pos
    r2 = delta.x * delta.x + delta.y * delta.y + softening
    return delta.normalized() * (gm / r2)


def graph_pressure_diffusion(
    zones: list[Zone], sinks: dict[int, float],
    dt: float, D: float = 0.08,
) -> None:
    """Eq. 3 -- Driller pressure graph (double-buffered)."""
    deltas = [0.0] * len(zones)
    for i, z in enumerate(zones):
        diff = sum(zones[j].pressure - z.pressure for j in z.neighbors)
        deltas[i] = (D * diff - sinks.get(z.id, 0.0)) * dt
    for i, z in enumerate(zones):
        z.pressure = max(0.0, z.pressure + deltas[i])


def hysteresis_failure(
    excess: float, pressure: float, critical: float,
    dt: float, threshold: float = 15.0,
    hyst_leak: float = 0.05,
) -> tuple[float, bool]:
    """Eq. 4 -- Failure is memory, not instant threshold. With leak for recovery."""
    excess += max(0.0, pressure - critical) * dt
    excess -= hyst_leak * excess * dt
    excess = max(0.0, excess)
    return excess, excess > threshold


def teleport_transform(
    pos: Vec2, vel: Vec2, target: Vec2, delta_heading_byte: int,
) -> tuple[Vec2, Vec2, int]:
    """Colony-style teleport with orientation transform."""
    delta_rad = (delta_heading_byte / 256.0) * TAU
    new_vel = vel.rotate(delta_rad)
    return target, new_vel, delta_heading_byte


def bresenham_los(
    x0: int, y0: int, x1: int, y1: int,
    grid: dict[tuple[int, int], Cell] | None = None,
) -> list[tuple[int, int]]:
    """Bresenham line-of-sight with optional wall-aware truncation."""
    cells: list[tuple[int, int]] = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    cx, cy = x0, y0
    while True:
        cells.append((cx, cy))
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            cx += sx
        if e2 <= dx:
            err += dx
            cy += sy
        # If grid provided, stop at furniture (LOS blocked by walls)
        if grid is not None:
            cell = grid.get((cx, cy))
            if cell and cell.furniture:
                break
    return cells


def colony_generate_grid(
    w: int, h: int, seed: int, wall_density: float = 0.45,
) -> dict[tuple[int, int], Cell]:
    """Procedural cell grid with teleport doors and energy stations."""
    rng = random.Random(seed)
    grid: dict[tuple[int, int], Cell] = {}
    for y in range(h):
        for x in range(w):
            walls = {"n": True, "s": True, "e": True, "w": True,
                     "u": False, "d": False}
            if x < w - 1 and rng.random() < (1.0 - wall_density):
                walls["e"] = False
            if y < h - 1 and rng.random() < (1.0 - wall_density):
                walls["s"] = False
            tp = None
            if rng.random() < 0.04:
                tx, ty = rng.randint(0, w - 1), rng.randint(0, h - 1)
                tp = (tx, ty)
            grid[(x, y)] = Cell(
                walls=walls,
                object_id=rng.randint(0, 3),
                furniture=rng.random() < 0.06,
                teleport_to=tp,
                energy_station=rng.random() < 0.05,
            )
    return grid


def procedural_starfield(
    seed: int, count: int, world_size: Vec2,
) -> list[Vec2]:
    """Deterministic universe: law + seed > stored map."""
    rng = random.Random(seed)
    return [Vec2(rng.random() * world_size.x, rng.random() * world_size.y)
            for _ in range(count)]


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Agent Policies
# ═══════════════════════════════════════════════════════════════════════════════


def agent_naive(step: int, rng: random.Random) -> int:
    """Random rotation ticks on a schedule."""
    if step % 32 == 0:
        return rng.choice([-8, -4, 4, 8])
    return 0


def agent_lander_pid(
    ship: Body, fuel: ResourceReservoir,
    pad_x: float, dt: float,
    prev_error: list[float],
) -> tuple[float, bool]:
    """PID controller targeting safe landing near pad."""
    target_vy = -1.5
    error = target_vy - ship.vel.y
    thrust = clamp(1.8 * error + 0.6 * (error - prev_error[0]), 0, 5.0)
    prev_error[0] = error
    dx = pad_x - ship.pos.x
    if abs(dx) > 8 and fuel.value > 20:
        ship.rotate_quantized(6 if dx > 0 else -6)
    return thrust, fuel.value > 0


def agent_colony_wall_follow(
    cx: int, cy: int, heading: int,
    grid: dict[tuple[int, int], Cell],
    gw: int, gh: int,
) -> tuple[int, int, int, bool]:
    """Right-hand rule wall follower for Colony mode."""
    sector = (heading + 32) % 256 // 64
    cell = grid.get((cx, cy))
    if cell is None:
        return cx, cy, 0, False

    # Try right
    r_wall = WALL_RIGHT[sector]
    r_sector = (sector + 1) % 4
    rdx, rdy, _ = SECTOR_DIRS[r_sector]
    if not cell.walls.get(r_wall, True):
        nx, ny = (cx + rdx) % gw, (cy + rdy) % gh
        target = grid.get((nx, ny))
        if target and not target.furniture:
            dh = 64 if r_sector > sector else -192
            return nx, ny, dh, True

    # Try forward
    fwall = SECTOR_DIRS[sector][2]
    fdx, fdy = SECTOR_DIRS[sector][0], SECTOR_DIRS[sector][1]
    if not cell.walls.get(fwall, True):
        nx, ny = (cx + fdx) % gw, (cy + fdy) % gh
        target = grid.get((nx, ny))
        if target and not target.furniture:
            return nx, ny, 0, True

    # Try left
    l_wall = WALL_LEFT[sector]
    l_sector = (sector + 3) % 4
    ldx, ldy, _ = SECTOR_DIRS[l_sector]
    if not cell.walls.get(l_wall, True):
        nx, ny = (cx + ldx) % gw, (cy + ldy) % gh
        target = grid.get((nx, ny))
        if target and not target.furniture:
            dh = -64 if l_sector < sector else 192
            return nx, ny, dh, True

    # Turn around
    return cx, cy, 128, False


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Prediction Model v4
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SignaturePredictor:
    """Tiny transition-based predictor -- retro-simple but stateful."""
    last: tuple | None = None
    transition_counts: Counter[tuple[tuple, tuple]] = field(default_factory=Counter)

    def predict(self, current: tuple) -> tuple | None:
        candidates = {
            nxt: count
            for (cur, nxt), count in self.transition_counts.items()
            if cur == current
        }
        if not candidates:
            return None
        return max(candidates, key=candidates.get)

    def update(self, current: tuple, actual_next: tuple) -> float:
        pred = self.predict(current)
        self.transition_counts[(current, actual_next)] += 1
        if pred is None:
            return 0.5
        return 0.0 if pred == actual_next else 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# 9. HDC Engine v4
# ═══════════════════════════════════════════════════════════════════════════════


class HDCEngine:
    """Lightweight HDC using bipolar vectors.
    v4: Gödel tokens are functional -- they buy repair trials via DLASc.
    """

    def __init__(self, dim: int = 1024, seed: int = 42):
        self.dim = dim
        self.rng = random.Random(seed)
        self.vectors: dict[str, list[int]] = {}
        self.memory = self._bipolar()
        self.godel_tokens: int = 0
        self.anomaly_count: int = 0

    def _bipolar(self) -> list[int]:
        return [1 if self.rng.random() < 0.5 else -1 for _ in range(self.dim)]

    def encode(self, name: str) -> list[int]:
        if name not in self.vectors:
            self.vectors[name] = self._bipolar()
        return self.vectors[name]

    @staticmethod
    def bind(a: list[int], b: list[int]) -> list[int]:
        return [x * y for x, y in zip(a, b)]

    @staticmethod
    def bundle(vecs: list[list[int]]) -> list[int]:
        if not vecs:
            return []
        n = len(vecs[0])
        s = [0] * n
        for v in vecs:
            for i in range(n):
                s[i] += v[i]
        return [1 if x >= 0 else -1 for x in s]

    @staticmethod
    def permute(v: list[int], shift: int = 1) -> list[int]:
        shift = shift % len(v)
        return v[shift:] + v[:shift]

    @staticmethod
    def similarity(a: list[int], b: list[int]) -> float:
        n = min(len(a), len(b))
        if n == 0:
            return 0.0
        return sum(a[i] * b[i] for i in range(n)) / n

    def drift(self, predicted: list[int], actual: list[int]) -> float:
        return 1.0 - self.similarity(predicted, actual)

    def inject_anomaly(self) -> list[int]:
        self.anomaly_count += 1
        a = self._bipolar()
        self.memory = self.bundle([self.memory, a])
        return a

    def exceptional_point(
        self, law_a: str, law_b: str, state_vec: list[int],
    ) -> float:
        sa = self.similarity(self.encode(law_a), state_vec)
        sb = self.similarity(self.encode(law_b), state_vec)
        return abs(sa - sb)

    def state_vector(
        self, mode: str, active_laws: list[str],
        metric_buckets: dict[str, bool],
    ) -> list[int]:
        parts = [self.encode(mode)]
        for ln in active_laws:
            parts.append(self.encode(ln))
        for bucket, present in metric_buckets.items():
            if present:
                parts.append(self.encode(bucket))
        return self.bundle(parts)

    def earn_godel_token(self, prediction_error: float,
                         drift_val: float,
                         anomaly_threshold: float) -> bool:
        """Functional anomaly mechanism:
        Prediction failure earns a Gödel token.
        Tokens can be spent by DLASc to test repair laws.
        """
        if prediction_error > anomaly_threshold or drift_val > anomaly_threshold:
            self.godel_tokens += 1
            return True
        return False

    def spend_godel_tokens(self, cost: int) -> bool:
        """Try to spend tokens for a repair trial."""
        if self.godel_tokens >= cost:
            self.godel_tokens -= cost
            return True
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 10. DLASc v4 -- Dynamic Law-Actuated Semantic Compiler
# ═══════════════════════════════════════════════════════════════════════════════


class DLASc:
    """Operates on LawStack, not global registry flags.
    Activation triggers map conditions to law additions.
    Deactivation triggers map conditions to law removals.
    """

    ACTIVATION_RULES: list[tuple[str, callable]] = []
    DEACTIVATION_RULES: list[tuple[str, callable]] = []

    def __init__(self, registry: dict[str, LawTerm]):
        self.registry = registry
        self.contribution_scores: dict[str, float] = defaultdict(float)
        self.execution_counts: dict[str, int] = defaultdict(int)
        self.step_count: int = 0

    def propose(self, state: SimState, t: Telemetry) -> list[str]:
        """Examine state and propose law additions/removals."""
        proposals: list[str] = []
        ctx = {
            "blocked_ratio": state.agent_stats.blocked / max(state.agent_stats.attempted, 1),
            "criticality": t.criticality,
            "prediction_error": t.prediction_error,
            "coverage": t.coverage,
            "law_count": t.law_count,
            "semantic_entropy": t.semantic_entropy,
            "step": state.step,
        }

        # Activation proposals
        if (ctx["blocked_ratio"] > 0.5 and
                "cell_grid" in [LAW_REGISTRY[n].preconditions[0]
                                for n in state.law_stack.names
                                if n in LAW_REGISTRY and LAW_REGISTRY[n].preconditions]):
            if not state.law_stack.has("wall_following_agent"):
                proposals.append("+wall_following_agent")

        if (ctx["criticality"] > 0.7 and
                "pressure_reservoir" in [LAW_REGISTRY[n].preconditions[0]
                                         for n in state.law_stack.names
                                         if n in LAW_REGISTRY and LAW_REGISTRY[n].preconditions]):
            if not state.law_stack.has("risk_policy"):
                proposals.append("+risk_policy")

        if (ctx["prediction_error"] > 0.3 and
                state.mode == "colony" and
                not state.law_stack.has("bresenham_los")):
            proposals.append("+bresenham_los")

        # Deactivation proposals
        for name in list(state.law_stack.names):
            if self.execution_counts[name] == 0 and self.step_count > 40:
                proposals.append(f"-{name}")
            elif self.contribution_scores[name] < -0.05 and self.step_count > 30:
                proposals.append(f"-{name}")

        return proposals

    def apply(self, state: SimState, proposals: list[str]) -> list[str]:
        """Apply proposals to the law stack. Returns list of changes."""
        changes: list[str] = []
        for p in proposals:
            if p.startswith("+"):
                name = p[1:]
                if name in LAW_REGISTRY:
                    cost = LAW_REGISTRY[name].token_cost
                    if (state.hdc is not None and
                            state.hdc.spend_godel_tokens(cost)):
                        state.law_stack.add(name)
                        changes.append(f"+{name}")
            elif p.startswith("-"):
                name = p[1:]
                state.law_stack.remove(name)
                changes.append(f"-{name}")
        return changes

    def tick(self, state: SimState, t: Telemetry) -> list[str]:
        """Full propose+apply cycle."""
        self.step_count += 1
        proposals = self.propose(state, t)
        changes = self.apply(state, proposals)
        return changes

    def record_execution(self, name: str) -> None:
        self.execution_counts[name] += 1

    def update_contribution(
        self, law: str, baseline_pr: float, ablated_pr: float,
    ) -> None:
        contrib = baseline_pr - ablated_pr
        # Rolling average
        old = self.contribution_scores[law]
        self.contribution_scores[law] = 0.7 * old + 0.3 * contrib


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Metrics Engine v4
# ═══════════════════════════════════════════════════════════════════════════════


def state_signature(
    x: float, y: float, z: float, speed: float,
    crit: float, zone: int, heading_byte: int,
    cell: str,
) -> tuple:
    return (
        round(x, 1), round(y, 1), round(z, 1),
        round(speed, 1), round(crit, 2), zone,
        heading_byte // 16, cell,
    )


def playable_reality_v4(
    state_density: float,
    goal_agency: float,
    falsifiability: float,
    compression_gain: float,
    law_stack: LawStack,
    registry: dict[str, LawTerm],
    ambiguity: float,
    semantic_entropy: float,
    prediction_error: float,
) -> tuple[float, float]:
    """Compute (PR_raw, PR_norm).
    PR_raw for internal comparisons.
    PR_norm comparable to v2/v3 outputs.
    """
    law_cost = law_stack.cost(registry)
    law_count = max(law_stack.count(), 1)
    mean_cost = law_cost / law_count

    raw = (
        state_density
        * clamp(goal_agency, 0.0, 1.0)
        * falsifiability
        * clamp(compression_gain, 0.01, 20.0)
    ) / max(
        law_cost * (1 + 0.3 * ambiguity +
                    0.15 * min(semantic_entropy, 5.0) +
                    0.3 * prediction_error),
        1e-9,
    )

    normalized = raw * mean_cost * law_count
    return raw, normalized


def falsifiability_v4(
    law_stack: LawStack, registry: dict[str, LawTerm],
) -> float:
    return law_stack.falsifiability(registry)


def semantic_entropy_v4(
    ambiguity: float, law_count: int, agency: float,
) -> float:
    return ambiguity * law_count / max(agency, 0.01)


def compression_gain_v4(
    step: int, seed_bytes: int, law_cost: float,
) -> float:
    return (step + 1) / max(seed_bytes + law_cost, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Mode Constructors
# ═══════════════════════════════════════════════════════════════════════════════


def make_state(mode: str, seed: int, config: SimConfig) -> SimState:
    """Create a SimState for the given mode."""
    agent_stats = AgentStats()
    hdc = HDCEngine(dim=config.hdc_dim, seed=seed)
    predictor = SignaturePredictor()

    if mode == "lander":
        state = _make_lander(seed, config)
    elif mode == "asteroids":
        state = _make_asteroids(seed, config)
    elif mode == "pressure":
        state = _make_pressure(seed, config)
    elif mode == "freescape":
        state = _make_freescape(seed, config)
    elif mode == "colony":
        state = _make_colony(seed, config)
    elif mode == "semantic":
        state = _make_semantic(seed, config)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Keep the law_stack set by the constructor (already has mode-specific laws)
    state.agent_stats = agent_stats
    state.hdc = hdc
    state.config = config
    state.seed = seed
    state.mode = mode
    state.step = 0
    state.extra["predictor"] = predictor
    state.extra["rng"] = random.Random(seed)
    return state


def _make_lander(seed: int, config: SimConfig) -> SimState:
    world = Vec2(160.0, 90.0)
    pad_x = world.x * 0.5
    ship = Body(pos=Vec2(pad_x + 20, world.y * 0.75), vel=Vec2(5.0, 0.0))
    ship.last_pos = Vec2(ship.pos.x, ship.pos.y)
    resources = {
        "fuel": ResourceReservoir(100.0, 100.0),
        "heat": ResourceReservoir(5.0, 100.0, leak=0.035, critical=90.0),
        "pressure": ResourceReservoir(25.0, 150.0, critical=120.0),
    }
    law_stack = LawStack(names=[
        "thrust_gravity_drag", "quantized_rotation",
        "resource_thermodynamics", "playable_reality",
    ])
    if config.adaptive:
        law_stack.add("pid_controller")
    return SimState(
        mode="lander", seed=seed, step=0, config=config,
        law_stack=law_stack, agent_stats=AgentStats(), hdc=None,
        body=ship, resources=resources,
        extra={"pad_x": pad_x, "world": world, "prev_error": [0.0]},
    )


def _make_asteroids(seed: int, config: SimConfig) -> SimState:
    world = Vec2(160.0, 90.0)
    ship = Body(pos=Vec2(world.x * 0.5, world.y * 0.75), vel=Vec2(5.0, 0.0))
    ship.last_pos = Vec2(ship.pos.x, ship.pos.y)
    resources = {
        "fuel": ResourceReservoir(100.0, 100.0),
        "heat": ResourceReservoir(5.0, 100.0, leak=0.035, critical=90.0),
        "pressure": ResourceReservoir(25.0, 150.0, critical=120.0),
    }
    law_stack = LawStack(names=[
        "central_gravity_well", "toroidal_wrap",
        "quantized_rotation", "resource_thermodynamics",
        "playable_reality",
    ])
    return SimState(
        mode="asteroids", seed=seed, step=0, config=config,
        law_stack=law_stack, agent_stats=AgentStats(), hdc=None,
        body=ship, resources=resources,
        extra={
            "world": world,
            "attractor": Vec2(world.x * 0.5, world.y * 0.5),
        },
    )


def _make_pressure(seed: int, config: SimConfig) -> SimState:
    world = Vec2(160.0, 90.0)
    ship = Body(pos=Vec2(world.x * 0.3, world.y * 0.5), vel=Vec2(2.0, 0.0))
    ship.last_pos = Vec2(ship.pos.x, ship.pos.y)
    resources = {
        "fuel": ResourceReservoir(100.0, 100.0),
        "heat": ResourceReservoir(5.0, 100.0, leak=0.035, critical=90.0),
        "pressure": ResourceReservoir(25.0, 150.0, critical=120.0),
    }
    zones = [
        Zone(id=0, pressure=25.0, neighbors=[1, 2]),
        Zone(id=1, pressure=40.0, neighbors=[0, 3, 4]),
        Zone(id=2, pressure=20.0, neighbors=[0, 5]),
        Zone(id=3, pressure=35.0, neighbors=[1]),
        Zone(id=4, pressure=50.0, neighbors=[1]),
        Zone(id=5, pressure=15.0, neighbors=[2]),
    ]
    law_stack = LawStack(names=[
        "thrust_gravity_drag", "graph_pressure_diffusion",
        "hysteresis_failure", "resource_thermodynamics",
        "playable_reality",
    ])
    if config.adaptive:
        law_stack.add("risk_policy")
    return SimState(
        mode="pressure", seed=seed, step=0, config=config,
        law_stack=law_stack, agent_stats=AgentStats(), hdc=None,
        body=ship, resources=resources, zones=zones,
        extra={"world": world, "excess_integral": 0.0, "peak_pressure": 25.0},
    )


def _make_freescape(seed: int, config: SimConfig) -> SimState:
    world3 = Vec3(64.0, 32.0, 64.0)
    body = Body3(
        pos=Vec3(32.0, 16.0, 32.0),
        vel=Vec3(0.5, 0.0, 0.3),
        heading_byte=64, zone_id=0,
    )
    body.last_pos = Vec3(body.pos.x, body.pos.y, body.pos.z)
    resources = {
        "fuel": ResourceReservoir(100.0, 100.0),
        "heat": ResourceReservoir(5.0, 100.0, leak=0.02, critical=90.0),
        "pressure": ResourceReservoir(25.0, 150.0, critical=120.0),
        "shield": ResourceReservoir(50.0, 50.0, critical=10.0),
    }
    zones = [
        Zone(id=0, gravity=1.0, friction=0.05, pressure=25.0, neighbors=[1, 3]),
        Zone(id=1, gravity=0.5, friction=0.10, pressure=40.0, neighbors=[0, 2]),
        Zone(id=2, gravity=0.1, friction=0.20, pressure=80.0, neighbors=[1]),
        Zone(id=3, gravity=2.0, friction=0.02, pressure=15.0, neighbors=[0, 4]),
        Zone(id=4, gravity=1.5, friction=0.08, pressure=60.0, neighbors=[3]),
    ]
    cuboids = [
        Cuboid(Vec3(20, 0, 20), Vec3(22, 20, 22)),
        Cuboid(Vec3(40, 0, 30), Vec3(42, 18, 50)),
        Cuboid(Vec3(10, 0, 40), Vec3(18, 12, 42)),
        Cuboid(Vec3(50, 0, 10), Vec3(52, 25, 30)),
    ]
    law_stack = LawStack(names=[
        "cuboid_collision", "zone_gravity_friction", "hydraulic_height",
        "graph_pressure_diffusion", "hysteresis_failure",
        "resource_thermodynamics", "playable_reality",
    ])
    return SimState(
        mode="freescape", seed=seed, step=0, config=config,
        law_stack=law_stack, agent_stats=AgentStats(), hdc=None,
        body3=body, resources=resources, zones=zones, cuboids=cuboids,
        extra={"world3": world3, "excess_integral": 0.0},
    )


def _make_colony(seed: int, config: SimConfig) -> SimState:
    grid_w, grid_h = 24, 24
    grid = colony_generate_grid(grid_w, grid_h, seed, config.wall_density)
    resources = {
        "fuel": ResourceReservoir(100.0, 100.0),
        "heat": ResourceReservoir(5.0, 100.0, leak=0.01, critical=90.0),
        "pressure": ResourceReservoir(25.0, 150.0, critical=120.0),
        "suit": ResourceReservoir(100.0, 100.0, leak=0.005, critical=15.0),
    }
    cx, cy = grid_w // 2, grid_h // 2
    law_stack = LawStack(names=[
        "cell_occupancy", "quantized_rotation", "toroidal_surface",
        "power_suit_energy", "resource_thermodynamics",
        "playable_reality",
    ])
    if config.adaptive:
        law_stack.add("wall_following_agent")
    return SimState(
        mode="colony", seed=seed, step=0, config=config,
        law_stack=law_stack, agent_stats=AgentStats(), hdc=None,
        resources=resources, grid=grid,
        visited_cells={(cx, cy)},
        extra={
            "cx": cx, "cy": cy, "heading": 64,
            "grid_w": grid_w, "grid_h": grid_h,
        },
    )


def _make_semantic(seed: int, config: SimConfig) -> SimState:
    resources = {
        "fuel": ResourceReservoir(100.0, 100.0),
        "heat": ResourceReservoir(5.0, 100.0),
        "pressure": ResourceReservoir(25.0, 150.0),
    }
    law_stack = LawStack(names=[
        "playable_reality", "minimum_law_efficiency",
        "compression_ratio", "semantic_entropy",
    ])
    return SimState(
        mode="semantic", seed=seed, step=0, config=config,
        law_stack=law_stack, agent_stats=AgentStats(), hdc=None,
        resources=resources,
        extra={"mode_results": {}},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Per-Mode Step Functions
# ═══════════════════════════════════════════════════════════════════════════════


def _build_telemetry(state: SimState) -> Telemetry:
    """Build telemetry from current SimState."""
    rng = state.extra.get("rng", random.Random(0))
    predictor: SignaturePredictor = state.extra.get("predictor", SignaturePredictor())
    dt = state.config.dt

    # Gather position/speed data
    if state.body is not None:
        x, y, z = state.body.pos.x, state.body.pos.y, state.body.height
        speed = state.body.vel.length()
        hb = state.body.heading_byte
        failure_state = state.body.state
    elif state.body3 is not None:
        x, y, z = state.body3.pos.x, state.body3.pos.y, state.body3.pos.z
        speed = state.body3.vel.length()
        hb = state.body3.heading_byte
        failure_state = state.body3.state
    else:
        x, y, z, speed, hb = 0.0, 0.0, 0.0, 0.0, 0
        failure_state = "active"

    fuel = state.resources.get("fuel", ResourceReservoir(0, 1)).value
    heat = state.resources.get("heat", ResourceReservoir(0, 1)).value
    pressure = state.resources.get("pressure", ResourceReservoir(0, 1)).value
    suit = state.resources.get("suit", ResourceReservoir(0, 1)).value
    shield = state.resources.get("shield", ResourceReservoir(0, 1)).value

    crit = max(
        state.resources.get("heat", ResourceReservoir(0, 1)).criticality,
        state.resources.get("pressure", ResourceReservoir(0, 1)).criticality,
        1.0 - state.resources.get("shield", ResourceReservoir(100, 100)).normalized()
        if "shield" in state.resources else 0.0,
    )

    # State signature for state density
    cell_pos = ""
    if "cx" in state.extra and "cy" in state.extra:
        cell_pos = f"({state.extra['cx']},{state.extra['cy']})"
    zone_id = 0
    if state.body3 is not None:
        zone_id = state.body3.zone_id
    elif state.body is not None:
        zone_id = state.body.zone_id

    sig = state_signature(x, y, z, speed, crit, zone_id, hb, cell_pos)
    state.signatures.add(sig)
    state_density = len(state.signatures) / max(state.step + 1, 1)

    # Prediction error via SignaturePredictor
    if predictor.last is not None:
        pred_error = predictor.update(predictor.last, sig)
    else:
        pred_error = 0.0
    predictor.last = sig

    # Coverage (for colony)
    coverage = len(state.visited_cells) / max(
        state.extra.get("grid_w", 1) * state.extra.get("grid_h", 1), 1,
    ) if state.visited_cells else 0.0

    # Agency from AgentStats
    action_ag = state.agent_stats.action_agency
    goal_ag = state.agent_stats.goal_agency
    ag = goal_ag if goal_ag > 0 else action_ag

    # Ambiguity = prediction error for now
    ambiguity = pred_error

    # Metrics
    fals = falsifiability_v4(state.law_stack, LAW_REGISTRY)
    se = semantic_entropy_v4(ambiguity, state.law_stack.count(), ag)
    cg = compression_gain_v4(state.step, 4, state.law_stack.cost(LAW_REGISTRY))
    pr_raw, pr_norm = playable_reality_v4(
        state_density, ag, fals, cg,
        state.law_stack, LAW_REGISTRY,
        ambiguity, se, pred_error,
    )
    mle = state_density / max(state.law_stack.count(), 1)

    # HDC
    godel_tokens = 0
    drift_val = 0.0
    delta_ep = 0.0
    if state.hdc is not None:
        buckets = {
            "high_agency": ag > 0.6,
            "low_agency": ag < 0.3,
            "high_entropy": se > 2.0,
            "critical_rising": crit > 0.5,
            "pr_good": pr_raw > 0.4,
            "coverage_good": coverage > 0.1,
        }
        sv = state.hdc.state_vector(state.mode, state.law_stack.names, buckets)
        drift_val = state.hdc.drift(state.hdc.memory, sv)
        state.hdc.memory = sv
        state.hdc.earn_godel_token(pred_error, drift_val, state.config.anomaly_threshold)
        godel_tokens = state.hdc.godel_tokens

        ep_pairs = [
            ("toroidal_wrap", "teleport_transform"),
            ("resource_thermodynamics", "hysteresis_failure"),
            ("cuboid_collision", "cell_occupancy"),
        ]
        delta_ep = min(
            (state.hdc.exceptional_point(a, b, sv) for a, b in ep_pairs),
            default=0.0,
        )

    return Telemetry(
        step=state.step, mode=state.mode, seed=state.seed,
        x=x, y=y, z=z, speed=speed,
        fuel=fuel, heat=heat, pressure=pressure,
        suit=suit, shield=shield,
        criticality=crit, pr=pr_raw, pr_norm=pr_norm, mle=mle,
        law_cost=state.law_stack.cost(LAW_REGISTRY),
        law_count=state.law_stack.count(),
        falsifiability=fals, semantic_entropy=se,
        prediction_error=pred_error,
        action_agency=action_ag, goal_agency=goal_ag,
        coverage=coverage, state_density=state_density,
        ambiguity=ambiguity, compression_gain=cg,
        godel_tokens=godel_tokens,
        semantic_drift=drift_val, delta_ep_min=delta_ep,
        active_laws=",".join(state.law_stack.names),
        failure_state=failure_state,
        zone_id=zone_id, heading_byte=hb, cell_pos=cell_pos,
    )


def step_lander(state: SimState) -> Telemetry:
    """Step Lander mode."""
    rng: random.Random = state.extra["rng"]
    dt = state.config.dt
    ship = state.body
    world: Vec2 = state.extra["world"]
    pad_x = state.extra["pad_x"]
    prev_error: list[float] = state.extra["prev_error"]
    fuel = state.resources["fuel"]
    heat = state.resources["heat"]

    prev_vy_error = abs(ship.vel.y - (-1.5))

    if state.config.adaptive and "pid_controller" in state.law_stack.names:
        thrust, attempted = agent_lander_pid(ship, fuel, pad_x, dt, prev_error)
        state.agent_stats.attempted += int(attempted)
        useful = abs(ship.vel.y + 1.5) < prev_vy_error
        state.agent_stats.useful += int(attempted and useful)
        state.agent_stats.moved += int(thrust > 0)
    else:
        ticks = agent_naive(state.step, rng)
        if ticks:
            ship.rotate_quantized(ticks)
        thrust = 3.8 if fuel.value > 0 and state.step % 9 in (0, 1, 2, 3) else 0.0
        state.agent_stats.attempted += 1
        state.agent_stats.moved += int(thrust > 0)
        useful = abs(ship.vel.y) < 3.0
        state.agent_stats.useful += int(thrust > 0 and useful)

    gravity = Vec2(0.0, -1.62)
    drag = 0.01
    fuel.step(dt, sink=0.9 if thrust else 0.0)
    heat.step(dt, source=0.35 if thrust else 0.0)
    arcade_motion_step(ship, dt, thrust, gravity, drag, world, wrap_edges=False)

    crit = max(heat.criticality, state.resources["pressure"].criticality)
    if crit >= 1.0 and ship.state == "active":
        ship.state = "exploded"
        state.agent_stats.failures += 1

    return _build_telemetry(state)


def step_asteroids(state: SimState) -> Telemetry:
    """Step Asteroids mode."""
    rng: random.Random = state.extra["rng"]
    dt = state.config.dt
    ship = state.body
    world: Vec2 = state.extra["world"]
    attractor: Vec2 = state.extra["attractor"]
    fuel = state.resources["fuel"]
    heat = state.resources["heat"]

    ticks = agent_naive(state.step, rng)
    if ticks:
        ship.rotate_quantized(ticks)
        state.agent_stats.attempted += 1
        state.agent_stats.moved += 1
        state.agent_stats.useful += 1

    gravity = central_gravity_well(ship, attractor, gm=85.0)
    thrust = 2.2 if state.step % 11 < 4 else 0.0
    state.agent_stats.attempted += 1
    state.agent_stats.moved += int(thrust > 0)
    # Goal agency: did thrust improve orbital distance stability?
    dist_to_attractor = ship.pos.distance_to(attractor)
    useful = thrust > 0 and 30 < dist_to_attractor < 80
    state.agent_stats.useful += int(useful)

    fuel.step(dt, sink=0.35 if thrust else 0.0)
    heat.step(dt, source=0.25 if thrust else 0.0,
              noise=rng.uniform(-0.02, 0.02))
    arcade_motion_step(ship, dt, thrust, gravity, 0.0, world, wrap_edges=True)

    return _build_telemetry(state)


def step_pressure(state: SimState) -> Telemetry:
    """Step Pressure mode."""
    rng: random.Random = state.extra["rng"]
    dt = state.config.dt
    ship = state.body
    world: Vec2 = state.extra["world"]
    fuel = state.resources["fuel"]
    heat = state.resources["heat"]
    pressure = state.resources["pressure"]
    excess: float = state.extra["excess_integral"]
    peak: float = state.extra["peak_pressure"]

    ticks = agent_naive(state.step, rng)
    if ticks:
        ship.rotate_quantized(ticks)

    thrust = 1.2 if fuel.value > 0 and state.step % 13 < 5 else 0.0
    gravity = Vec2(0.0, -0.4)
    drag = 0.08
    fuel.step(dt, sink=0.25 if thrust else 0.0)
    heat.step(dt, source=0.15 if thrust else 0.0)
    pressure.step(dt, source=state.config.pressure_source,
                  noise=rng.uniform(-0.1, 0.1))

    drilling = (state.config.drill_power
                if state.step in range(70, 95) or state.step in range(155, 180)
                else 0.0)
    sinks = {0: drilling, 1: drilling * 0.5, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
    graph_pressure_diffusion(state.zones, sinks, dt)

    excess, exploded = hysteresis_failure(
        excess, pressure.value, pressure.critical, dt,
    )
    state.extra["excess_integral"] = excess
    peak = max(peak, pressure.value)
    state.extra["peak_pressure"] = peak

    if exploded and ship.state == "active":
        ship.state = "exploded"
        state.agent_stats.failures += 1

    arcade_motion_step(ship, dt, thrust, gravity, drag, world, wrap_edges=False)

    state.agent_stats.attempted += 1
    state.agent_stats.moved += int(thrust > 0 or drilling > 0)
    # Goal agency: did drilling reduce pressure?
    pressure_recovery = max(0, peak - pressure.value) / max(peak - 25.0, 1e-9)
    state.agent_stats.useful += int(drilling > 0 and pressure_recovery > 0.1)

    return _build_telemetry(state)


def step_freescape(state: SimState) -> Telemetry:
    """Step Freescape mode."""
    rng: random.Random = state.extra["rng"]
    dt = state.config.dt
    body = state.body3
    world3: Vec3 = state.extra["world3"]
    fuel = state.resources["fuel"]
    heat = state.resources["heat"]
    pressure = state.resources["pressure"]
    shield = state.resources["shield"]
    excess: float = state.extra["excess_integral"]

    if state.step % 24 == 0:
        body.rotate_quantized(rng.choice([-12, -6, 6, 12]))

    # Zone from position (v4 fix: not timer)
    zone_idx = min(int(body.pos.x / world3.x * len(state.zones)),
                   len(state.zones) - 1)
    body.zone_id = zone_idx
    z = state.zones[zone_idx]

    thrust_active = state.step % 7 < 3
    if thrust_active:
        rad = body.heading_rad
        body.vel.x += math.cos(rad) * 0.15 * z.time_scale
        body.vel.z += math.sin(rad) * 0.15 * z.time_scale

    fuel.step(dt, sink=0.4 if thrust_active else 0.0)
    heat.step(dt, source=0.2 if thrust_active else 0.0)
    motion_step_3d(body, dt, z.gravity, z.friction, world3)

    for c in state.cuboids:
        hit, new_vel = cuboid_collide(body.pos, body.vel, c)
        if hit:
            body.vel = new_vel
            body.collision_count += 1

    graph_pressure_diffusion(state.zones,
                            {zone_idx: 2.0 if thrust_active else 0.0}, dt)
    pressure.value = z.pressure

    if z.pressure > 60:
        shield.step(dt, sink=0.5)
    else:
        shield.step(dt, source=0.1)

    excess, exploded = hysteresis_failure(excess, pressure.value,
                                           pressure.critical, dt)
    state.extra["excess_integral"] = excess
    if exploded and body.state == "active":
        body.state = "exploded"
        state.agent_stats.failures += 1

    # Hydraulic height lift
    if body.pos.y < 2.0 and z.id == 3:
        body.vel.y = 3.0

    state.agent_stats.attempted += 1
    state.agent_stats.moved += int(thrust_active)
    useful = (body.pos.distance_to(body.last_pos) > 0.3
              or body.collision_count > state.extra.get("prev_collisions", 0))
    state.agent_stats.useful += int(useful)
    state.extra["prev_collisions"] = body.collision_count

    return _build_telemetry(state)


def step_colony(state: SimState) -> Telemetry:
    """Step Colony mode."""
    rng: random.Random = state.extra["rng"]
    dt = state.config.dt
    cx: int = state.extra["cx"]
    cy: int = state.extra["cy"]
    heading: int = state.extra["heading"]
    gw: int = state.extra["grid_w"]
    gh: int = state.extra["grid_h"]
    grid = state.grid
    suit = state.resources["suit"]
    fuel = state.resources["fuel"]
    heat = state.resources["heat"]

    moved = False
    if state.step % 6 == 0:
        if state.config.adaptive and "wall_following_agent" in state.law_stack.names:
            new_cx, new_cy, dh, moved = agent_colony_wall_follow(
                cx, cy, heading, grid, gw, gh,
            )
        else:
            sector = (heading + 32) % 256 // 64
            dx, dy, wall_key = SECTOR_DIRS[sector]
            cell = grid.get((cx, cy))
            if cell and not cell.walls.get(wall_key, True):
                nx, ny = (cx + dx) % gw, (cy + dy) % gh
                target = grid.get((nx, ny))
                if target and target.teleport_to is not None:
                    new_cx, new_cy, dh, moved = target.teleport_to[0], target.teleport_to[1], 0, True
                else:
                    new_cx, new_cy, dh, moved = nx, ny, 0, True
            else:
                new_cx, new_cy, dh, moved = cx, cy, 16, False

        if moved and new_cx != cx or new_cy != cy:
            state.visited_cells.add((new_cx, new_cy))
        heading = (heading + dh) % 256
        state.extra["cx"] = new_cx
        state.extra["cy"] = new_cy
        state.extra["heading"] = heading

        if moved:
            state.agent_stats.moved += 1
        else:
            state.agent_stats.blocked += 1
        state.agent_stats.attempted += 1
        # Goal agency: new cell visited
        state.agent_stats.useful += int(
            moved and (new_cx, new_cy) in state.visited_cells
        )

    if state.step % 18 == 0:
        heading = (heading + rng.choice([-16, -8, 8, 16])) % 256
        state.extra["heading"] = heading

    # Energy station
    cur_cx, cur_cy = state.extra["cx"], state.extra["cy"]
    cell = grid.get((cur_cx, cur_cy))
    if cell and cell.energy_station:
        suit.step(dt, source=3.0)
    suit.step(dt)
    fuel.step(dt, sink=0.1)
    heat.step(dt, source=0.05)

    if suit.is_critical():
        state.agent_stats.failures += 1

    return _build_telemetry(state)


def step_semantic(state: SimState) -> Telemetry:
    """Step Semantic mode -- live cross-mode analytics."""
    dt = state.config.dt
    results: dict = state.extra.get("mode_results", {})

    # Simulate a tiny version of each mode every step cycle
    mode_idx = state.step % 6
    mode_name = BASE_MODES[mode_idx]
    mini_config = SimConfig(dt=dt, max_steps=1)
    mini_state = make_state(mode_name, state.seed, mini_config)
    mini_state.hdc = None  # no nested HDC
    t = step_sim(mini_state)
    results[mode_name] = {
        "pr": t.pr_norm,
        "agency": t.goal_agency,
        "law_cost": t.law_cost,
        "coverage": t.coverage,
    }
    state.extra["mode_results"] = results

    # Semantic: aggregate stats
    avg_pr = sum(r["pr"] for r in results.values()) / max(len(results), 1)
    return Telemetry(
        step=state.step, mode="semantic", seed=state.seed,
        pr=avg_pr, pr_norm=avg_pr,
        law_cost=sum(r["law_cost"] for r in results.values()) / max(len(results), 1),
        law_count=4,
        state_density=len(results) / 6.0,
        goal_agency=sum(r["agency"] for r in results.values()) / max(len(results), 1),
        coverage=sum(r["coverage"] for r in results.values()) / max(len(results), 1),
        active_laws="playable_reality,minimum_law_efficiency,compression_ratio,semantic_entropy",
        failure_state="active",
    )


def step_sim(state: SimState) -> Telemetry:
    """Dispatch to the correct step function."""
    step_fn = {
        "lander": step_lander,
        "asteroids": step_asteroids,
        "pressure": step_pressure,
        "freescape": step_freescape,
        "colony": step_colony,
        "semantic": step_semantic,
    }.get(state.mode)

    if step_fn is None:
        raise ValueError(f"No step function for mode: {state.mode}")

    t = step_fn(state)
    state.step += 1
    state.history.append(t)
    return t


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Simulation Runner
# ═══════════════════════════════════════════════════════════════════════════════


def run_sim(
    mode: str, seed: int, steps: int,
    config: SimConfig | None = None,
    dlas: DLASc | None = None,
) -> list[Telemetry]:
    """Run a full simulation and return telemetry list."""
    if config is None:
        config = SimConfig(max_steps=steps)
    state = make_state(mode, seed, config)
    out: list[Telemetry] = []

    for _ in range(steps + 1):
        t = step_sim(state)
        # DLASc adaptive tick
        if dlas is not None and config.adaptive and state.step % 10 == 0:
            changes = dlas.tick(state, t)
            if changes:
                t.events = " ".join(changes)
        out.append(t)

        # Early exit on failure (stress mode)
        if config.stress and t.failure_state != "active":
            break

    return out


def final_pr(telemetry: list[Telemetry]) -> float:
    """Get the final PR_norm from a telemetry list."""
    return telemetry[-1].pr_norm if telemetry else 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Audit and Optimizer Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def estimate_law_contribution(
    mode: str, seed: int, config: SimConfig,
    law: str, window: int = 80,
) -> float:
    """Cheap ablation: PR_full - PR_without_law."""
    baseline = run_sim(mode, seed, window, config)
    patched_config = SimConfig(
        dt=config.dt, adaptive=config.adaptive,
        agent_policy=config.agent_policy,
        wall_density=config.wall_density,
        hdc_dim=config.hdc_dim, max_steps=window,
    )
    # Create state and remove the law
    state = make_state(mode, seed, patched_config)
    if law in state.law_stack.names:
        state.law_stack.remove(law)
    # Run manually
    out: list[Telemetry] = []
    for _ in range(window + 1):
        t = step_sim(state)
        out.append(t)
        if t.failure_state != "active":
            break
    return final_pr(baseline) - final_pr(out)


def audit_mode(
    mode: str, seed: int, steps: int,
    config: SimConfig | None = None,
) -> dict[str, Any]:
    """Compute per-law contribution analysis for a mode."""
    if config is None:
        config = SimConfig(max_steps=steps)
    state = make_state(mode, seed, config)
    dlas = DLASc(LAW_REGISTRY)

    for _ in range(steps + 1):
        t = step_sim(state)
        if config.adaptive and state.step % 10 == 0:
            dlas.tick(state, t)
        # Track which laws executed
        for ln in state.law_stack.names:
            dlas.record_execution(ln)
        if t.failure_state != "active":
            break

    contributions: dict[str, dict[str, Any]] = {}
    for law in state.law_stack.names:
        contrib = estimate_law_contribution(mode, seed, config, law, window=min(steps, 80))
        contributions[law] = {
            "contribution": round(contrib, 4),
            "executed": dlas.execution_counts[law] > 0,
            "execution_count": dlas.execution_counts[law],
            "verdict": "keep" if contrib > 0 else "remove",
        }

    dead_laws = [
        name for name, info in contributions.items()
        if info["contribution"] <= 0 or not info["executed"]
    ]
    total_cost = state.law_stack.cost(LAW_REGISTRY)

    return {
        "mode": mode,
        "seed": seed,
        "steps": len(state.history),
        "final_pr": round(final_pr(state.history), 4),
        "final_pr_norm": round(state.history[-1].pr_norm if state.history else 0, 4),
        "law_cost": round(total_cost, 2),
        "law_count": state.law_stack.count(),
        "coverage": round(state.history[-1].coverage if state.history else 0, 4),
        "goal_agency": round(state.history[-1].goal_agency if state.history else 0, 4),
        "contributions": contributions,
        "dead_laws": dead_laws,
        "active_laws": state.law_stack.names,
    }


def optimize_mode(
    mode: str, seed: int, episodes: int,
    config: SimConfig | None = None,
) -> dict[str, Any]:
    """Grid search over wall_density and agent_policy."""
    if config is None:
        config = SimConfig()
    best_pr = -1.0
    best_params: dict[str, Any] = {}
    results: list[dict] = []

    densities = [0.30, 0.40, 0.45, 0.55, 0.65]
    policies = ["naive", "wall_follow"]

    for ep in range(episodes):
        ep_seed = seed + ep
        for wd in densities:
            for pol in policies:
                cfg = SimConfig(
                    dt=config.dt,
                    adaptive=(pol != "naive"),
                    agent_policy=pol,
                    wall_density=wd,
                    max_steps=config.max_steps,
                    hdc_dim=config.hdc_dim,
                )
                tel = run_sim(mode, ep_seed, config.max_steps, cfg)
                pr = final_pr(tel)
                ag = tel[-1].goal_agency if tel else 0
                cov = tel[-1].coverage if tel else 0
                lc = tel[-1].law_cost if tel else 0
                results.append({
                    "episode": ep, "seed": ep_seed,
                    "wall_density": wd, "policy": pol,
                    "pr": round(pr, 4), "agency": round(ag, 4),
                    "coverage": round(cov, 4), "law_cost": round(lc, 2),
                })
                if pr > best_pr:
                    best_pr = pr
                    best_params = {
                        "wall_density": wd, "policy": pol,
                        "seed": ep_seed, "pr": round(pr, 4),
                    }

    results.sort(key=lambda r: r["pr"], reverse=True)
    return {
        "mode": mode,
        "episodes": episodes,
        "best_params": best_params,
        "best_pr": round(best_pr, 4),
        "top_5": results[:5],
        "all_results": results,
    }


def stress_mode(
    mode: str, seed: int, max_steps: int,
    config: SimConfig | None = None,
) -> dict[str, Any]:
    """Run until failure or max_steps. Measure TTF."""
    if config is None:
        config = SimConfig(max_steps=max_steps, stress=True)
    else:
        config = SimConfig(
            dt=config.dt, adaptive=config.adaptive,
            agent_policy=config.agent_policy,
            wall_density=config.wall_density,
            hdc_dim=config.hdc_dim,
            max_steps=max_steps, stress=True,
        )
    tel = run_sim(mode, seed, max_steps, config)
    ttf = len(tel)
    failed = any(t.failure_state != "active" for t in tel)
    failure_step = next(
        (t.step for t in tel if t.failure_state != "active"),
        -1,
    )
    failure_reason = ""
    if failed:
        ft = next(t for t in tel if t.failure_state != "active")
        failure_reason = ft.failure_state

    return {
        "mode": mode,
        "seed": seed,
        "ttf": ttf,
        "max_steps": max_steps,
        "failed": failed,
        "failure_step": failure_step,
        "failure_reason": failure_reason,
        "final_pr": round(final_pr(tel), 4) if tel else 0,
        "final_coverage": round(tel[-1].coverage, 4) if tel else 0,
        "final_agency": round(tel[-1].goal_agency, 4) if tel else 0,
        "telemetry_count": len(tel),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Campaign Runners
# ═══════════════════════════════════════════════════════════════════════════════


def run_campaign_baseline(
    seed: int, steps: int,
    config: SimConfig | None = None,
) -> dict[str, list[Telemetry]]:
    """Run all modes with minimal static stacks."""
    if config is None:
        config = SimConfig(adaptive=False, max_steps=steps)
    else:
        config = SimConfig(
            dt=config.dt, adaptive=False,
            agent_policy=config.agent_policy,
            wall_density=config.wall_density,
            hdc_dim=config.hdc_dim, max_steps=steps,
        )
    results: dict[str, list[Telemetry]] = {}
    for mode in BASE_MODES:
        results[mode] = run_sim(mode, seed, steps, config)
    return results


def run_campaign_adaptive(
    seed: int, steps: int,
    config: SimConfig | None = None,
) -> dict[str, list[Telemetry]]:
    """Run all modes with DLASc + HDC tokens enabled."""
    if config is None:
        config = SimConfig(adaptive=True, max_steps=steps)
    else:
        config = SimConfig(
            dt=config.dt, adaptive=True,
            agent_policy=config.agent_policy,
            wall_density=config.wall_density,
            hdc_dim=config.hdc_dim, max_steps=steps,
        )
    results: dict[str, list[Telemetry]] = {}
    for mode in BASE_MODES:
        dlas = DLASc(LAW_REGISTRY)
        results[mode] = run_sim(mode, seed, steps, config, dlas=dlas)
    return results


def run_campaign_stress(
    mode: str, seed: int, max_steps: int,
    config: SimConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """Stress test a single mode across multiple seeds."""
    if config is None:
        config = SimConfig(adaptive=True, stress=True)
    results: dict[str, dict[str, Any]] = {}
    for s in range(seed, seed + 5):
        results[f"seed_{s}"] = stress_mode(mode, s, max_steps, config)
    return results


def run_campaign_audit(
    mode: str, seed: int, steps: int,
    config: SimConfig | None = None,
) -> dict[str, Any]:
    """Full audit of a single mode."""
    return audit_mode(mode, seed, steps, config)


def run_campaign_optimize(
    mode: str, seed: int, episodes: int,
    config: SimConfig | None = None,
) -> dict[str, Any]:
    """Optimize parameters for a single mode."""
    return optimize_mode(mode, seed, episodes, config)


def run_campaign_compare(
    seed: int, steps: int,
    config: SimConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """Compare baseline vs adaptive vs optimized for all modes."""
    if config is None:
        config = SimConfig(max_steps=steps)
    baseline = run_campaign_baseline(seed, steps, config)
    adaptive = run_campaign_adaptive(seed, steps, config)

    comparison: dict[str, dict[str, Any]] = {}
    for mode in BASE_MODES:
        bl = baseline[mode]
        ad = adaptive[mode]

        # Quick optimization (fewer episodes)
        opt = optimize_mode(mode, seed, episodes=10,
                           config=SimConfig(
                               dt=config.dt, max_steps=steps,
                               wall_density=config.wall_density,
                               hdc_dim=config.hdc_dim,
                           ))

        comparison[mode] = {
            "pr_base": round(final_pr(bl), 4),
            "pr_adapt": round(final_pr(ad), 4),
            "pr_opt": round(opt["best_pr"], 4),
            "delta_opt": round(opt["best_pr"] - final_pr(bl), 4),
            "agency_base": round(bl[-1].goal_agency, 4) if bl else 0,
            "agency_adapt": round(ad[-1].goal_agency, 4) if ad else 0,
            "coverage_base": round(bl[-1].coverage, 4) if bl else 0,
            "coverage_adapt": round(ad[-1].coverage, 4) if ad else 0,
            "law_cost_base": round(bl[-1].law_cost, 2) if bl else 0,
            "law_cost_adapt": round(ad[-1].law_cost, 2) if ad else 0,
            "best_params": opt.get("best_params", {}),
            "dead_laws": opt.get("best_params", {}),
        }

    return {"baseline": baseline, "adaptive": adaptive, "comparison": comparison}


# ═══════════════════════════════════════════════════════════════════════════════
# 17. Export Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def write_csv(telemetry: list[Telemetry], path: str) -> None:
    """Write telemetry to CSV."""
    if not telemetry:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=telemetry[0].csv_row().keys())
        writer.writeheader()
        for t in telemetry:
            writer.writerow(t.csv_row())


def write_json(summary: dict[str, Any], path: str) -> None:
    """Write summary to JSON."""
    with open(path, "w") as f:
        json.dump(summary, f, indent=2, default=str)


def write_markdown_report(
    data: dict[str, Any], path: str,
) -> None:
    """Write a markdown report from campaign/compare results."""
    lines: list[str] = []
    lines.append("# RGPUF Lab v4 -- Micro-World Forge Report\n")
    lines.append("core: rgpuf_core.py | demo: rgpuf_lab_v4.py\n")

    if "comparison" in data:
        lines.append("\n## Mode Comparison\n")
        lines.append("")
        header = (
            f"{'MODE':<12} {'PR_BASE':>8} {'PR_ADAPT':>8} {'PR_OPT':>8} "
            f"{'DELTA':>7} {'AGENCY':>7} {'COVER':>6} {'LAW_COST':>8}\n"
        )
        lines.append(header)
        lines.append("-" * len(header))

        for mode, info in data["comparison"].items():
            lines.append(
                f"{mode:<12} {info['pr_base']:8.3f} {info['pr_adapt']:8.3f} "
                f"{info['pr_opt']:8.3f} {info['delta_opt']:+7.3f} "
                f"{info['agency_adapt']:7.2f} {info['coverage_adapt']:6.2f} "
                f"{info['law_cost_adapt']:8.1f}"
            )

    # Law contribution sections
    if "baseline" in data:
        lines.append("\n## Detailed Mode Analysis\n")
        for mode in BASE_MODES:
            tel = data["baseline"].get(mode, [])
            if not tel:
                continue
            last = tel[-1]
            lines.append(f"\n### {mode}\n")
            lines.append(f"- Final PR (normalized): {last.pr_norm:.4f}")
            lines.append(f"- Final PR (raw): {last.pr:.4f}")
            lines.append(f"- Goal Agency: {last.goal_agency:.4f}")
            lines.append(f"- Coverage: {last.coverage:.4f}")
            lines.append(f"- Law Cost: {last.law_cost:.2f}")
            lines.append(f"- Laws: {last.active_laws}")
            lines.append(f"- Gödel Tokens: {last.godel_tokens}")
            lines.append(f"- Failure: {last.failure_state}")

    # Best micro-world recipe
    if "comparison" in data:
        lines.append("\n## Best Micro-World Recipes\n")
        for mode, info in data["comparison"].items():
            bp = info.get("best_params", {})
            if bp:
                lines.append(f"\n### {mode.title()}\n")
                lines.append(f"- Seed: {bp.get('seed', '?')}")
                lines.append(f"- Wall Density: {bp.get('wall_density', '?')}")
                lines.append(f"- Policy: {bp.get('policy', '?')}")
                lines.append(f"- PR: {bp.get('pr', '?')}")

    with open(path, "w") as f:
        f.write("\n".join(lines))


# ═══════════════════════════════════════════════════════════════════════════════
# 18. Display Utilities
# ═══════════════════════════════════════════════════════════════════════════════


def sparkline(v: float, w: int = 14, mx: float = 1.0) -> str:
    f = int(round(clamp(v / max(mx, 1e-9), 0, 1) * w))
    return "\u2588" * f + "\u2591" * (w - f)


def print_telemetry(t: Telemetry, interval: int = 12) -> None:
    """Print a telemetry frame to terminal."""
    if t.step % interval != 0:
        return
    if t.mode == "colony":
        line = (
            f"t={t.step:03d} {t.mode:<9} cell={t.cell_pos} h={t.heading_byte:03d} "
            f"suit={t.suit:5.1f} ag_act={t.action_agency:.2f} ag_goal={t.goal_agency:.2f} "
            f"cov={t.coverage:.2f} PR={t.pr_norm:.3f} cost={t.law_cost:.1f}"
        )
    elif t.mode == "freescape":
        line = (
            f"t={t.step:03d} {t.mode:<9} z={t.zone_id:02d} "
            f"({t.x:5.1f},{t.y:5.1f},{t.z:4.1f}) spd={t.speed:5.2f} "
            f"ag={t.goal_agency:.2f} PR={t.pr_norm:.3f} laws={t.law_count}"
        )
    else:
        line = (
            f"t={t.step:03d} {t.mode:<9} "
            f"({t.x:6.1f},{t.y:6.1f}) spd={t.speed:6.2f} "
            f"ag={t.goal_agency:.2f} PR={t.pr_norm:.3f} "
            f"fals={t.falsifiability:.2f} cost={t.law_cost:.1f}"
        )
    if t.godel_tokens > 0:
        line += f" \u26a0{t.godel_tokens}"
    if t.events:
        line += f" [{t.events}]"
    print(line)
