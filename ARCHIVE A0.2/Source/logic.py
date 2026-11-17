
GRID_SIZE = 40


# ==========================================
# ROTATION
# ==========================================

def rotate_point(point, rotation):
    """Rotate a local point in 90-degree steps."""
    x, y = point

    for _ in range(rotation % 4):
        # Counterclockwise on a Pygame screen
        x, y = y, -x

    return (x, y)


def transform_point(position, offset, rotation):
    dx, dy = rotate_point(offset, rotation)
    return (position[0] + dx, position[1] + dy)


# ==========================================
# COMPONENTS
# ==========================================

class Lever:
    def __init__(self, position):
        self.position = position
        self.on = False

    def toggle(self):
        self.on = not self.on


class Wire:
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.on = False
        self.king = None


class NotGate:
    def __init__(self, position, rotation=0):
        self.position = position
        self.rotation = rotation % 4
        self.input = False
        self.output = True
        self.input_king = None

    def point(self, offset):
        return transform_point(
            self.position, offset, self.rotation
        )

    @property
    def input_position(self):
        return self.point((-GRID_SIZE, 0))

    @property
    def output_position(self):
        return self.point((GRID_SIZE, 0))

    @property
    def on(self):
        return self.output


class AndGate:
    def __init__(self, position, rotation=0):
        self.position = position
        self.rotation = rotation % 4

        self.input_a = False
        self.input_b = False
        self.output = False

        self.king_a = None
        self.king_b = None

    def point(self, offset):
        return transform_point(
            self.position, offset, self.rotation
        )

    @property
    def input_a_position(self):
        return self.point((-GRID_SIZE, -GRID_SIZE))

    @property
    def input_b_position(self):
        return self.point((-GRID_SIZE, GRID_SIZE))

    @property
    def output_position(self):
        return self.point((GRID_SIZE, 0))

    @property
    def on(self):
        return self.output


# ==========================================
# KING
# ==========================================

class King:
    def __init__(self, id):
        self.id = id
        self.wires = []
        self.power_sources = []
        self.on = False

    def update(self):
        self.on = any(
            source.on for source in self.power_sources
        )

        for wire in self.wires:
            wire.on = self.on


# ==========================================
# CIRCUIT
# ==========================================

class Circuit:
    def __init__(self):
        self.levers = []
        self.wires = []
        self.not_gates = []
        self.and_gates = []
        self.kings = []

    def add_lever(self, position):
        for lever in self.levers:
            if lever.position == position:
                return lever

        lever = Lever(position)
        self.levers.append(lever)
        self.rebuild()
        return lever

    def add_wire(self, start, end):
        if start == end:
            return None

        for wire in self.wires:
            if {wire.start, wire.end} == {start, end}:
                return wire

        wire = Wire(start, end)
        self.wires.append(wire)
        self.rebuild()
        return wire

    def add_not_gate(self, position, rotation=0):
        for gate in self.not_gates + self.and_gates:
            if gate.position == position:
                return None

        gate = NotGate(position, rotation)
        self.not_gates.append(gate)
        self.rebuild()
        return gate

    def add_and_gate(self, position, rotation=0):
        for gate in self.not_gates + self.and_gates:
            if gate.position == position:
                return None

        gate = AndGate(position, rotation)
        self.and_gates.append(gate)
        self.rebuild()
        return gate

    def toggle_lever(self, position):
        for lever in self.levers:
            if lever.position == position:
                lever.toggle()
                self.update()
                return True

        return False

    def update(self):
        # Start with default gate output states.
        for gate in self.not_gates:
            gate.output = True

        for gate in self.and_gates:
            gate.output = False

        gates = self.not_gates + self.and_gates
        max_steps = len(gates) + 2

        for _ in range(max_steps):
            for king in self.kings:
                king.update()

            changes = []

            for gate in self.not_gates:
                gate.input = (
                    gate.input_king.on
                    if gate.input_king is not None
                    else False
                )
                changes.append((gate, not gate.input))

            for gate in self.and_gates:
                gate.input_a = (
                    gate.king_a.on
                    if gate.king_a is not None
                    else False
                )
                gate.input_b = (
                    gate.king_b.on
                    if gate.king_b is not None
                    else False
                )

                changes.append((
                    gate,
                    gate.input_a and gate.input_b
                ))

            changed = any(
                gate.output != value
                for gate, value in changes
            )

            for gate, value in changes:
                gate.output = value

            if not changed:
                break

        for king in self.kings:
            king.update()

        for gate in self.not_gates:
            gate.input = (
                gate.input_king.on
                if gate.input_king is not None
                else False
            )

        for gate in self.and_gates:
            gate.input_a = (
                gate.king_a.on
                if gate.king_a is not None
                else False
            )
            gate.input_b = (
                gate.king_b.on
                if gate.king_b is not None
                else False
            )

    def rebuild(self):
        self.kings = []
        connections = {}

        for wire in self.wires:
            wire.king = None
            wire.on = False

            connections.setdefault(
                wire.start, []
            ).append(wire)

            connections.setdefault(
                wire.end, []
            ).append(wire)

        visited = set()
        point_to_king = {}

        for wire in self.wires:
            if wire in visited:
                continue

            king = King(len(self.kings) + 1)
            stack = [wire]

            while stack:
                current = stack.pop()

                if current in visited:
                    continue

                visited.add(current)
                current.king = king
                king.wires.append(current)

                for point in (
                    current.start, current.end
                ):
                    point_to_king[point] = king

                    for neighbor in connections[point]:
                        if neighbor not in visited:
                            stack.append(neighbor)

            self.kings.append(king)

        for lever in self.levers:
            king = point_to_king.get(lever.position)
            if king is not None:
                king.power_sources.append(lever)

        for gate in self.not_gates:
            gate.input_king = point_to_king.get(
                gate.input_position
            )

            output_king = point_to_king.get(
                gate.output_position
            )

            if output_king is not None:
                output_king.power_sources.append(gate)

        for gate in self.and_gates:
            gate.king_a = point_to_king.get(
                gate.input_a_position
            )

            gate.king_b = point_to_king.get(
                gate.input_b_position
            )

            output_king = point_to_king.get(
                gate.output_position
            )

            if output_king is not None:
                output_king.power_sources.append(gate)

        self.update()


# ==========================================
# PCB WIRE ROUTING
# ==========================================

def route_wire(start, end):
    x1, y1 = start
    x2, y2 = end

    dx = x2 - x1
    dy = y2 - y1

    if start == end:
        return []

    if dx == 0 or dy == 0:
        return [start, end]

    if abs(dx) == abs(dy):
        return [start, end]

    sx = 1 if dx > 0 else -1
    sy = 1 if dy > 0 else -1

    corner = min(
        GRID_SIZE, abs(dx), abs(dy)
    )

    points = [
        start,
        (x2 - sx * corner, y1),
        (x2, y1 + sy * corner),
        end
    ]

    cleaned = []

    for point in points:
        if not cleaned or point != cleaned[-1]:
            cleaned.append(point)

    return cleaned
