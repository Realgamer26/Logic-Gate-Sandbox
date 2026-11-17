
"""Shared dark drawing for View and Render, including light bloom."""
import math
import pygame
import numpy as np

from logic import NotGate, AndGate, Delayer, rotated

BG = (12, 16, 25)
WHITE = (223, 232, 243)
GREEN = (76, 226, 134)
LIGHT_RADIUS = 14


def gaussian(image, sigma):
    n = max(1, round(3 * sigma))
    offsets = np.arange(-n, n + 1)
    weights = np.exp(-offsets * offsets / (2 * sigma * sigma))
    weights /= weights.sum()
    result = image.astype(np.float32)

    for axis in (0, 1):
        pad = [(0, 0)] * 3
        pad[axis] = (n, n)
        padded = np.pad(result, pad, mode='constant')
        new = np.zeros_like(result)

        for i, weight in enumerate(weights):
            if axis == 0:
                new += weight * padded[
                    i:i + result.shape[0], :, :
                ]
            else:
                new += weight * padded[
                    :, i:i + result.shape[1], :
                ]

        result = new

    return result


def bloom_surface(emission):
    w, h = emission.get_size()

    small = pygame.transform.smoothscale(
        emission, (max(1, w // 4), max(1, h // 4))
    )

    pixels = pygame.surfarray.array3d(
        small
    ).astype(np.float32)

    power = pixels.max(axis=2, keepdims=True)
    bright = pixels * np.clip(
        (power - 45) / 150, 0, 1
    )

    glow = np.clip(
        gaussian(bright, 2.5) * 0.95 +
        gaussian(bright, 7) * 0.8,
        0, 255
    ).astype(np.uint8)

    return pygame.transform.smoothscale(
        pygame.surfarray.make_surface(glow), (w, h)
    )


def polygon(surface, obj, local_points, to_screen,
            color, line_color=WHITE, width=2):
    pts = []

    for x, y in local_points:
        dx, dy = rotated((x, y), obj.rotation)
        pts.append(to_screen((
            obj.position[0] + dx,
            obj.position[1] + dy
        )))

    pygame.draw.polygon(surface, color, pts)
    pygame.draw.polygon(
        surface, line_color, pts, max(1, width)
    )


def draw_lever(surface, center, zoom, on):
    r = max(4, round(12 * zoom))

    pygame.draw.circle(
        surface, GREEN if on else (195, 142, 72),
        center, r
    )
    pygame.draw.circle(
        surface, WHITE, center, r,
        max(1, round(2 * zoom))
    )

    reach = round(7 * zoom)

    pygame.draw.line(
        surface, (30, 46, 55),
        (center[0] - reach, center[1] + reach),
        (center[0] + reach, center[1] - reach),
        max(1, round(3 * zoom))
    )


def draw_push_button(surface, center, zoom, pressed):
    side = max(4, round(40 * zoom))
    r = pygame.Rect(
        center[0] - side // 2,
        center[1] - side // 2,
        side, side
    )

    pygame.draw.rect(
        surface, (54, 65, 80), r,
        border_radius=max(1, round(3 * zoom))
    )
    pygame.draw.rect(
        surface, WHITE, r, max(1, round(2 * zoom))
    )

    for dx in (-14, 14):
        for dy in (-14, 14):
            pygame.draw.circle(
                surface, (20, 25, 33),
                (
                    center[0] + round(dx * zoom),
                    center[1] + round(dy * zoom)
                ),
                max(1, round(2.5 * zoom))
            )

    pygame.draw.circle(
        surface,
        GREEN if pressed else (146, 164, 183),
        center, max(3, round(11 * zoom))
    )
    pygame.draw.circle(
        surface, WHITE, center,
        max(3, round(11 * zoom)),
        max(1, round(2 * zoom))
    )


def draw_light(surface, center, zoom, on):
    side = max(4, round(40 * zoom))
    rect = pygame.Rect(
        center[0] - side // 2,
        center[1] - side // 2,
        side, side
    )

    pygame.draw.rect(surface, (48, 57, 69), rect)
    pygame.draw.rect(
        surface, WHITE, rect, max(1, round(2 * zoom))
    )
    pygame.draw.circle(
        surface,
        (255, 240, 165) if on else (74, 79, 90),
        center, max(2, round(14 * zoom))
    )


def draw_delayer(surface, gate, to_screen, zoom):
    pts = [
        to_screen(gate.port(q))
        for q in ((-40, -26), (40, 0), (-40, 26))
    ]

    pygame.draw.polygon(
        surface, (179, 192, 203), pts
    )

    # Fill the selected fraction of the triangle.
    coverage = (gate.delay_index + 1) / 4
    threshold = -40 + 80 * coverage
    tri = [(-40, -26), (40, 0), (-40, 26)]

    def intersect(a, b):
        t = (threshold - a[0]) / (b[0] - a[0])
        return (
            threshold,
            a[1] + (b[1] - a[1]) * t
        )

    clipped = []

    for i, current in enumerate(tri):
        previous = tri[i - 1]
        ci = current[0] <= threshold
        pi = previous[0] <= threshold

        if ci:
            if not pi:
                clipped.append(intersect(previous, current))
            clipped.append(current)
        elif pi:
            clipped.append(intersect(previous, current))

    if len(clipped) >= 3:
        fillpts = [
            to_screen(gate.port(v)) for v in clipped
        ]
        pygame.draw.polygon(
            surface,
            GREEN if gate.on else (66, 75, 86),
            fillpts
        )

    pygame.draw.polygon(
        surface, WHITE, pts, max(1, round(2 * zoom))
    )

    for pos in (
        gate.input_position, gate.output_position
    ):
        pygame.draw.circle(
            surface,
            GREEN if gate.on else WHITE,
            to_screen(pos),
            max(2, round(3 * zoom))
        )




def draw_capacitor(surface, capacitor, to_screen, zoom):
    """Rotating body, always-upright percentage."""

    from logic import GRID

    charge = max(0.0, min(100.0, capacitor.charge))

    # The rectangle rotates with the capacitor.
    corners = [
        capacitor.port((-GRID, -60)),
        capacitor.port((GRID, -60)),
        capacitor.port((GRID, 60)),
        capacitor.port((-GRID, 60))
    ]
    points = [to_screen(p) for p in corners]

    pygame.draw.polygon(surface, (34, 53, 74), points)

    # A green bar fills the body as charge increases.
    if charge > 0:
        bottom = 60
        top = 60 - 120 * charge / 100.0

        fill_corners = [
            capacitor.port((-GRID + 4, top)),
            capacitor.port((GRID - 4, top)),
            capacitor.port((GRID - 4, bottom - 4)),
            capacitor.port((-GRID + 4, bottom - 4))
        ]

        pygame.draw.polygon(
            surface, (65, 185, 106),
            [to_screen(p) for p in fill_corners]
        )

    pygame.draw.polygon(
        surface, WHITE, points,
        max(1, round(2 * zoom))
    )

    # Input and output arrows rotate with the body.
    def arrow(start, end):
        a = to_screen(start)
        b = to_screen(end)

        pygame.draw.line(
            surface, WHITE, a, b,
            max(1, round(3 * zoom))
        )

        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.hypot(dx, dy)

        if length:
            ux, uy = dx / length, dy / length
            size = max(5, round(10 * zoom))
            side = size * 0.55

            left = (
                b[0] - ux * size - uy * side,
                b[1] - uy * size + ux * side
            )
            right = (
                b[0] - ux * size + uy * side,
                b[1] - uy * size - ux * side
            )

            pygame.draw.polygon(
                surface, WHITE, [b, left, right]
            )

    arrow(
        capacitor.input_position,
        capacitor.port((0, -60))
    )
    arrow(
        capacitor.port((0, 60)),
        capacitor.output_position
    )

    # The text is drawn in screen coordinates,
    # so it NEVER rotates.
    center = to_screen(capacitor.position)
    font = pygame.font.SysFont(
        "consolas",
        max(10, round(20 * zoom)),
        bold=True
    )

    text = font.render(
        f"{charge:.0f}%", True, (255, 255, 255)
    )

    # Dark backing keeps the number readable.
    label_rect = text.get_rect(center=center)
    backing = label_rect.inflate(8, 5)

    pygame.draw.rect(
        surface, (21, 33, 45),
        backing,
        border_radius=3
    )

    surface.blit(text, label_rect)


def draw_transistor(surface, transistor, to_screen, zoom):
    """Three-terminal transistor with a rotating internal switch."""

    center = to_screen(transistor.position)
    radius = max(8, round(26 * zoom))
    width = max(1, round(2 * zoom))

    pygame.draw.circle(
        surface, (36, 54, 75), center, radius
    )
    pygame.draw.circle(
        surface, WHITE, center, radius, width
    )

    # Power leads and control lead.
    for offset, port in (
        ((-26, 0), transistor.input_position),
        ((26, 0), transistor.output_position),
        ((0, -26), transistor.control_position)
    ):
        pygame.draw.line(
            surface, WHITE,
            to_screen(transistor.port(offset)),
            to_screen(port),
            max(1, round(3 * zoom))
        )

    # Control is the switch command; input supplies power.
    # The line lies across the path when OFF,
    # and follows the path when ON.
    control_on = getattr(transistor, "control_on", False)
    if not control_on:
        control_on = getattr(transistor, "_display_control", False)

    if control_on:
        a, b = (-15, 0), (15, 0)
    else:
        a, b = (0, -15), (0, 15)

    pygame.draw.line(
        surface,
        GREEN if control_on else (245, 178, 100),
        to_screen(transistor.port(a)),
        to_screen(transistor.port(b)),
        max(2, round(4 * zoom))
    )

    for port in (
        transistor.input_position,
        transistor.output_position,
        transistor.control_position
    ):
        pygame.draw.circle(
            surface, WHITE,
            to_screen(port),
            max(2, round(3 * zoom))
        )

def draw_gate(surface, gate, to_screen, zoom, circuit=None):
    """Draw smooth gate bodies and connected terminal leads."""

    if isinstance(gate, Delayer):
        draw_delayer(surface, gate, to_screen, zoom)
        return

    stroke = max(1, round(2 * zoom))
    lead_width = max(1, round(3 * zoom))

    def point(x, y):
        return to_screen(gate.port((x, y)))

    def curve(start, control, end, steps=24):
        result = []

        for i in range(steps + 1):
            t = i / steps
            u = 1 - t

            x = (
                u * u * start[0]
                + 2 * u * t * control[0]
                + t * t * end[0]
            )
            y = (
                u * u * start[1]
                + 2 * u * t * control[1]
                + t * t * end[1]
            )

            result.append((x, y))

        return result

    def draw_body(local_points):
        screen_points = [
            point(x, y) for x, y in local_points
        ]

        pygame.draw.polygon(
            surface, (40, 60, 80), screen_points
        )
        pygame.draw.polygon(
            surface, WHITE, screen_points, stroke
        )

    def draw_lead(start, end, powered=False):
        pygame.draw.line(
            surface,
            GREEN if powered else WHITE,
            to_screen(start),
            to_screen(end),
            lead_width
        )

    def input_on(position):
        if circuit is None:
            return False
        return circuit.signal_at(position)

    if isinstance(gate, NotGate):
        # Standard triangular NOT gate.
        draw_body([
            (-22, -22),
            (24, 0),
            (-22, 22)
        ])

        pygame.draw.circle(
            surface, WHITE,
            point(29, 0),
            max(2, round(5 * zoom)),
            stroke
        )

        draw_lead(
            gate.input_position,
            gate.port((-22, 0)),
            input_on(gate.input_position)
        )
        draw_lead(
            gate.port((34, 0)),
            gate.output_position,
            gate.on
        )

        ports = [
            gate.input_position,
            gate.output_position
        ]

    else:
        if gate.kind in ('AND', 'NAND'):
            # D-shaped AND gate with a smooth semicircle.
            body = [(-22, -26), (-2, -26)]

            for i in range(25):
                angle = (
                    -math.pi / 2
                    + math.pi * i / 24
                )

                body.append((
                    -2 + 26 * math.cos(angle),
                    26 * math.sin(angle)
                ))

            body.append((-22, 26))

            input_a_join = (-22, -12)
            input_b_join = (-22, 12)
            tip_x = 24

        else:
            # OR, NOR and XOR use smooth Bezier curves.
            top = curve(
                (-22, -26),
                (10, -30),
                (26, 0)
            )

            bottom = curve(
                (26, 0),
                (10, 30),
                (-22, 26)
            )

            back = curve(
                (-22, 26),
                (-7, 0),
                (-22, -26)
            )

            body = top + bottom[1:] + back[1:]

            input_a_join = (-15, -12)
            input_b_join = (-15, 12)
            tip_x = 26

        draw_body(body)

        if gate.kind == 'XOR':
            # Extra curved line behind an XOR gate.
            extra = curve(
                (-30, -26),
                (-15, 0),
                (-30, 26)
            )

            pygame.draw.lines(
                surface, WHITE, False,
                [point(x, y) for x, y in extra],
                stroke
            )

        draw_lead(
            gate.input_a_position,
            gate.port(input_a_join),
            input_on(gate.input_a_position)
        )
        draw_lead(
            gate.input_b_position,
            gate.port(input_b_join),
            input_on(gate.input_b_position)
        )

        if gate.kind in ('NAND', 'NOR'):
            # Output inversion bubble.
            bubble_x = tip_x + 6

            pygame.draw.circle(
                surface, WHITE,
                point(bubble_x, 0),
                max(2, round(5 * zoom)),
                stroke
            )

            output_start = gate.port((
                bubble_x + 5, 0
            ))

        else:
            output_start = gate.port((
                tip_x, 0
            ))

        draw_lead(
            output_start,
            gate.output_position,
            gate.on
        )

        ports = [
            gate.input_a_position,
            gate.input_b_position,
            gate.output_position
        ]

    # Small terminal dots, exactly where wires connect.
    for i, port in enumerate(ports):
        powered = (
            gate.on
            if i == len(ports) - 1
            else input_on(port)
        )

        pygame.draw.circle(
            surface,
            GREEN if powered else WHITE,
            to_screen(port),
            max(2, round(3 * zoom))
        )



def draw_dark_mode(surface, circuit, to_screen,
                   zoom, show_circuit=False):
    surface.fill(BG)

    if show_circuit:
        for wire in circuit.wires:
            pygame.draw.line(
                surface,
                GREEN if wire.on else WHITE,
                to_screen(wire.start),
                to_screen(wire.end),
                max(1, round(2 * zoom))
            )

        for junction in circuit.junctions:
            center = to_screen(junction.position)

            pygame.draw.circle(
                surface, (235, 65, 65),
                center, max(3, round(5 * zoom))
            )

            pygame.draw.circle(
                surface, WHITE,
                center, max(3, round(5 * zoom)), 1
            )

        for capacitor in circuit.capacitors:
            draw_capacitor(
                surface, capacitor, to_screen, zoom
            )

        for transistor in circuit.transistors:
            transistor._display_control = circuit.signal_at(
                transistor.control_position
            )
            draw_transistor(
                surface, transistor, to_screen, zoom
            )

        for gate in (
            circuit.not_gates +
            circuit.and_gates +
            circuit.delayers
        ):
            draw_gate(
                surface, gate, to_screen, zoom, circuit
            )

    for lever in circuit.levers:
        draw_lever(
            surface,
            to_screen(lever.position),
            zoom, lever.on
        )

    for button in circuit.buttons:
        draw_push_button(
            surface,
            to_screen(button.position),
            zoom, button.on
        )

    emission = pygame.Surface(surface.get_size())
    emission.fill((0, 0, 0))

    for light in circuit.lights:
        point = to_screen(light.position)
        draw_light(surface, point, zoom, light.on)

        if light.on:
            pygame.draw.circle(
                emission, (255, 230, 110),
                point, max(2, round(14 * zoom))
            )

    if any(light.on for light in circuit.lights):
        surface.blit(
            bloom_surface(emission), (0, 0),
            special_flags=pygame.BLEND_RGB_ADD
        )

        for light in circuit.lights:
            if light.on:
                point = to_screen(light.position)

                pygame.draw.circle(
                    surface, (255, 245, 185),
                    point, max(2, round(14 * zoom))
                )
                pygame.draw.circle(
                    surface, (255, 255, 230),
                    point, max(1, round(7 * zoom))
                )


def draw_render_mode(surface, circuit, to_screen, zoom):
    draw_dark_mode(
        surface, circuit, to_screen,
        zoom, show_circuit=False
    )
