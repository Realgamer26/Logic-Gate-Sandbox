
"""Logic Gate Sandbox Alpha 0.7.1: digital networks and junctions."""

from collections import deque

GRID = 40
DELAYS = (0.1, 0.2, 0.5, 1.0)


def rotated(offset, turn):
    x, y = offset
    for _ in range(turn % 4):
        x, y = -y, x
    return x, y


def world(center, offset, turn=0):
    x, y = rotated(offset, turn)
    return (center[0] + x, center[1] + y)


class Component:
    def __init__(self, position, rotation=0):
        self.position = tuple(position)
        self.rotation = rotation % 4
        self.on = False

    def port(self, offset):
        return world(self.position, offset, self.rotation)


class Lever(Component):
    def toggle(self):
        self.on = not self.on


class Button(Component):
    def press(self):
        self.on = True

    def release(self):
        self.on = False


class Light(Component):
    pass


class Wire:
    def __init__(self, start, end, group_id=None):
        self.start = tuple(start)
        self.end = tuple(end)
        self.group_id = group_id
        self.on = False


class NotGate(Component):
    @property
    def input_position(self):
        return self.port((-GRID, 0))

    @property
    def output_position(self):
        return self.port((GRID, 0))


class AndGate(Component):
    TYPES = ('AND', 'OR', 'XOR', 'NOR', 'NAND')

    def __init__(self, position, rotation=0, kind='AND'):
        super().__init__(position, rotation)
        self.kind = kind.upper()
        if self.kind not in self.TYPES:
            raise ValueError('Invalid gate type')

    @property
    def input_a_position(self):
        return self.port((-GRID, -GRID))

    @property
    def input_b_position(self):
        return self.port((-GRID, GRID))

    @property
    def output_position(self):
        return self.port((GRID, 0))

    def evaluate(self, a, b):
        if self.kind == 'AND':
            return a and b
        if self.kind == 'OR':
            return a or b
        if self.kind == 'XOR':
            return a != b
        if self.kind == 'NOR':
            return not (a or b)
        return not (a and b)


class Delayer(Component):
    """Propagates each input edge after a selected amount of time."""

    def __init__(self, position, rotation=0, delay_index=0):
        super().__init__(position, rotation)
        self.delay_index = int(delay_index) % len(DELAYS)
        self.last_input = False
        self.events = deque()

    @property
    def delay(self):
        return DELAYS[self.delay_index]

    @property
    def input_position(self):
        return self.port((-GRID, 0))

    @property
    def output_position(self):
        return self.port((GRID, 0))

    def cycle(self):
        self.delay_index = (self.delay_index + 1) % len(DELAYS)


class Capacitor(Component):
    CHARGE_TIME = 10.0
    DISCHARGE_TIME = 10.0

    def __init__(self, position, rotation=0, charge=0.0):
        super().__init__(position, rotation)
        self.charge = max(0.0, min(100.0, float(charge)))
        self.on = self.charge > 0

    @property
    def input_position(self):
        return self.port((0, -2 * GRID))

    @property
    def output_position(self):
        return self.port((0, 2 * GRID))


class Transistor(Component):
    def __init__(self, position, rotation=0):
        super().__init__(position, rotation)

    @property
    def input_position(self):
        return self.port((-GRID, 0))

    @property
    def output_position(self):
        return self.port((GRID, 0))

    @property
    def control_position(self):
        return self.port((0, -GRID))


class Junction:
    """Connects all wires crossing its position."""

    def __init__(self, position, junction_id):
        self.position = tuple(position)
        self.id = junction_id
        self.on = False

    def __repr__(self):
        return (
            f"Junction(id={self.id}, "
            f"position={self.position})"
        )


class Circuit:
    def __init__(self):
        self.levers = []
        self.buttons = []
        self.lights = []
        self.wires = []
        self.not_gates = []
        self.and_gates = []
        self.delayers = []
        self.capacitors = []
        self.transistors = []
        self.junctions = []

        self.next_junction_id = 10000
        self.next_wire_group_id = 1

        self.time = 0.0
        self._net = {}
        self._net_values = {}
        self._wire_net = {}
        self._junction_net = {}

    def add_junction(self, position):
        position = tuple(position)

        for junction in self.junctions:
            if junction.position == position:
                return junction

        junction = Junction(
            position,
            self.next_junction_id
        )

        self.next_junction_id += 1
        self.junctions.append(junction)

        self.rebuild()
        return junction

    def remove_junction(self, junction):
        if junction in self.junctions:
            self.junctions.remove(junction)
            self.rebuild()

    def components(self):
        return (
            self.levers
            + self.buttons
            + self.lights
            + self.not_gates
            + self.and_gates
            + self.delayers + self.capacitors + self.transistors
        )

    def terminals(self):
        coords = []

        for obj in self.levers + self.buttons + self.lights:
            coords.append(obj.position)

        for obj in self.not_gates + self.delayers + self.capacitors:
            coords.extend((
                obj.input_position,
                obj.output_position
            ))

        for obj in self.transistors:
            coords.extend((
                obj.input_position,
                obj.output_position,
                obj.control_position
            ))

        for obj in self.and_gates:
            coords.extend((
                obj.input_a_position,
                obj.input_b_position,
                obj.output_position
            ))

        return coords

    def rebuild(self):
        """
        Separate wire groups are independent.

        Junctions connect all wire groups that touch them.
        Components connect to wires through their terminals.
        """

        parent = {}

        def root(node):
            if node not in parent:
                parent[node] = node

            if parent[node] != node:
                parent[node] = root(parent[node])

            return parent[node]

        def unite(left, right):
            a = root(left)
            b = root(right)

            if a != b:
                parent[b] = a

        # Each drawn wire group has its own electrical network.
        wire_nodes = {}

        for index, wire in enumerate(self.wires):
            identity = (
                wire.group_id
                if wire.group_id is not None
                else ('old', index)
            )

            node = ('wire', identity)

            wire_nodes[wire] = node
            root(node)

        # Connect separate wires if their ENDPOINTS match.
        # Crossings and T-intersections still need junctions.
        endpoints = {}

        for wire in self.wires:
            for point in (wire.start, wire.end):
                endpoints.setdefault(point, []).append(
                    wire_nodes[wire]
                )

        for nodes in endpoints.values():
            for node in nodes[1:]:
                unite(nodes[0], node)

        # Components make connections at their terminals.
        positions = set(map(tuple, self.terminals()))

        for point in positions:
            terminal = ('terminal', point)
            root(terminal)

            for wire in self.wires:
                if point_on_wire(point, wire):
                    unite(terminal, wire_nodes[wire])

        # Junctions connect all intersecting wire groups.
        for junction in self.junctions:
            touching = [
                wire_nodes[wire]
                for wire in self.wires
                if point_on_wire(junction.position, wire)
            ]

            if touching:
                for node in touching[1:]:
                    unite(touching[0], node)

        self._wire_net = {
            wire: root(node)
            for wire, node in wire_nodes.items()
        }

        self._net = {
            point: root(('terminal', point))
            for point in positions
        }

        self._junction_net = {}

        for junction in self.junctions:
            touching = [
                wire
                for wire in self.wires
                if point_on_wire(junction.position, wire)
            ]

            self._junction_net[junction] = (
                self._wire_net[touching[0]]
                if touching else None
            )

        self._net_values = {}
        self.update(0)

    def net_at(self, point):
        return self._net.get(tuple(point), tuple(point))

    def signal_at(self, point):
        return bool(
            self._net_values.get(self.net_at(point), False)
        )

    def update(self, dt=0):
        dt = max(0.0, float(dt))
        self.time += dt

        for capacitor in self.capacitors:
            capacitor.on = capacitor.charge > 0

        # Process delayed output events.
        for gate in self.delayers:
            while (
                gate.events
                and gate.events[0][0] <= self.time + 1e-9
            ):
                _, gate.on = gate.events.popleft()

        sources = (
            self.levers
            + self.buttons
            + self.not_gates
            + self.and_gates
            + self.delayers + self.capacitors + self.transistors
        )

        # Propagate signals through logic gates.
        iterations = max(
            3,
            2 * (
                len(self.not_gates)
                + len(self.and_gates)
            ) + 3
        )

        for _ in range(iterations):
            values = {}

            for obj in sources:
                if isinstance(
                    obj,
                    (NotGate, AndGate, Delayer, Capacitor, Transistor)
                ):
                    position = obj.output_position
                else:
                    position = obj.position

                net = self.net_at(position)

                values[net] = (
                    values.get(net, False) or obj.on
                )

            self._net_values = values
            changes = []

            for gate in self.not_gates:
                wanted = not self.signal_at(
                    gate.input_position
                )
                changes.append((gate, wanted))

            for gate in self.and_gates:
                wanted = gate.evaluate(
                    self.signal_at(gate.input_a_position),
                    self.signal_at(gate.input_b_position)
                )
                changes.append((gate, wanted))

            for transistor in self.transistors:
                wanted = (
                    self.signal_at(transistor.input_position)
                    and self.signal_at(transistor.control_position)
                )
                changes.append((transistor, wanted))

            if all(
                gate.on == wanted
                for gate, wanted in changes
            ):
                break

            for gate, wanted in changes:
                gate.on = wanted

        # Rebuild the final signal values.
        values = {}

        for obj in sources:
            if isinstance(
                obj,
                (NotGate, AndGate, Delayer, Capacitor, Transistor)
            ):
                position = obj.output_position
            else:
                position = obj.position

            net = self.net_at(position)

            values[net] = (
                values.get(net, False) or obj.on
            )

        self._net_values = values

        # Wires consume no power.
        # Each connected light drains 10% per second.
        changed_power = False

        for capacitor in self.capacitors:
            was_on = capacitor.on

            if self.signal_at(capacitor.input_position):
                capacitor.charge = min(
                    100.0,
                    capacitor.charge + 10.0 * dt
                )
            else:
                output_net = self.net_at(
                    capacitor.output_position
                )

                lights = sum(
                    self.net_at(light.position) == output_net
                    for light in self.lights
                )

                capacitor.charge = max(
                    0.0,
                    capacitor.charge - 10.0 * lights * dt
                )

            capacitor.on = capacitor.charge > 0
            changed_power |= capacitor.on != was_on

        if changed_power:
            self.update(0)
            return

        for gate in self.delayers:
            new_input = self.signal_at(
                gate.input_position
            )

            if new_input != gate.last_input:
                gate.last_input = new_input

                gate.events.append((
                    self.time + gate.delay,
                    new_input
                ))

        # Each wire reads its own electrical network.
        for wire in self.wires:
            net = self._wire_net.get(wire)

            wire.on = bool(
                self._net_values.get(net, False)
            )

        # Junctions show their connected signal.
        for junction in self.junctions:
            net = self._junction_net.get(junction)

            junction.on = bool(
                self._net_values.get(net, False)
            )

        for light in self.lights:
            light.on = self.signal_at(light.position)

    def add(self, kind, position, rotation=0):
        if kind == 'wire':
            raise ValueError('Use add_wire for wires')

        if kind == 'lever':
            obj, destination = Lever(position), self.levers

        elif kind == 'button':
            obj, destination = Button(position), self.buttons

        elif kind == 'light':
            obj, destination = Light(position), self.lights

        elif kind == 'not':
            obj, destination = (
                NotGate(position, rotation),
                self.not_gates
            )

        elif kind == 'transistor':
            obj, destination = (
                Transistor(position, rotation),
                self.transistors
            )

        elif kind == 'capacitor':
            obj, destination = (
                Capacitor(position, rotation),
                self.capacitors
            )

        elif kind == 'delayer':
            obj, destination = (
                Delayer(position, rotation),
                self.delayers
            )

        else:
            obj, destination = (
                AndGate(position, rotation, kind),
                self.and_gates
            )

        if any(
            overlaps(obj, other)
            for other in self.components()
        ):
            return None

        destination.append(obj)
        self.rebuild()
        return obj

    def new_wire_group(self):
        group_id = self.next_wire_group_id

        self.next_wire_group_id += 1
        return group_id

    def add_wire(self, start, end, group_id=None):
        start = tuple(start)
        end = tuple(end)

        if start == end:
            return None

        if group_id is None:
            group_id = self.new_wire_group()

        wire = Wire(start, end, group_id)

        self.wires.append(wire)
        self.rebuild()

        return wire

    def remove(self, objects):
        objects = set(objects)

        for name in (
            'levers',
            'buttons',
            'lights',
            'wires',
            'not_gates',
            'and_gates',
            'delayers', 'capacitors', 'transistors',
            'junctions'
        ):
            setattr(
                self,
                name,
                [
                    obj
                    for obj in getattr(self, name)
                    if obj not in objects
                ]
            )

        self.rebuild()


def point_on_wire(point, wire):
    """Check whether a point lies anywhere on a wire."""

    px, py = point
    ax, ay = wire.start
    bx, by = wire.end

    dx = bx - ax
    dy = by - ay

    cross = (
        (px - ax) * dy
        - (py - ay) * dx
    )

    if abs(cross) > 0.000001:
        return False

    return (
        min(ax, bx) <= px <= max(ax, bx)
        and min(ay, by) <= py <= max(ay, by)
    )


def footprint(obj):
    """Physical silhouette, excluding terminal leads."""

    p = obj.position
    r = obj.rotation

    if isinstance(obj, Transistor):
        local = [
            (-26, -26), (26, -26),
            (26, 26), (-26, 26)
        ]

    elif isinstance(obj, Capacitor):
        local = [
            (-40, -60), (40, -60),
            (40, 60), (-40, 60)
        ]

    elif isinstance(obj, Delayer):
        local = [
            (-40, -26), (40, 0), (-40, 26)
        ]

    elif isinstance(obj, NotGate):
        local = [
            (-22, -22), (24, 0), (-22, 22)
        ]

    elif isinstance(obj, AndGate):
        local = [
            (-24, -28), (27, -28),
            (27, 28), (-24, 28)
        ]

    elif isinstance(obj, (Button, Light)):
        local = [
            (-20, -20), (20, -20),
            (20, 20), (-20, 20)
        ]

    else:
        local = [
            (-14, -14), (14, -14),
            (14, 14), (-14, 14)
        ]

    return [
        world(p, xy, r)
        for xy in local
    ]


def overlaps(a, b):
    """Separating-axis collision test."""

    ap = footprint(a)
    bp = footprint(b)

    for poly in (ap, bp):
        for i, (x1, y1) in enumerate(poly):
            x2, y2 = poly[(i + 1) % len(poly)]

            axis = (
                -(y2 - y1),
                x2 - x1
            )

            av = [
                x * axis[0] + y * axis[1]
                for x, y in ap
            ]

            bv = [
                x * axis[0] + y * axis[1]
                for x, y in bp
            ]

            if (
                max(av) <= min(bv) + 1e-6
                or max(bv) <= min(av) + 1e-6
            ):
                return False

    return True


def wire_route(a, b):
    """
    Route with at most one 40px diagonal bend.

    A perfectly 45-degree line remains straight.
    Other routes use horizontal, diagonal,
    and vertical sections.
    """

    a = tuple(a)
    b = tuple(b)

    dx = b[0] - a[0]
    dy = b[1] - a[1]

    if dx == 0 and dy == 0:
        return []

    if (
        dx == 0
        or dy == 0
        or abs(dx) == abs(dy)
    ):
        return [(a, b)]

    direction_x = 1 if dx > 0 else -1
    direction_y = 1 if dy > 0 else -1

    diagonal = min(
        GRID,
        abs(dx),
        abs(dy)
    )

    first = (
        b[0] - direction_x * diagonal,
        a[1]
    )

    second = (
        b[0],
        a[1] + direction_y * diagonal
    )

    points = (a, first, second, b)

    return [
        (start, end)
        for start, end in zip(
            points,
            points[1:]
        )
        if start != end
    ]
