
import math
import pygame

from logic import (
    Circuit, Lever, NotGate, AndGate, route_wire
)

pygame.init()

# ==========================================
# WINDOW
# ==========================================

WIDTH, HEIGHT = 1000, 700

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Logic Gate Sandbox")

clock = pygame.time.Clock()

font = pygame.font.SysFont("consolas", 24)
small_font = pygame.font.SysFont("consolas", 16)
title_font = pygame.font.SysFont(
    "consolas", 48, bold=True
)

# ==========================================
# COLORS
# ==========================================

BACKGROUND = (27, 79, 145)
GRID_COLOR = (75, 125, 180)
WHITE = (255, 255, 255)

WIRE_OFF = (180, 180, 180)
WIRE_ON = (80, 255, 120)
LEVER_OFF = (255, 190, 60)

GATE_FILL = (20, 55, 95)
SELECT_RED = (255, 65, 65)

PREVIEW_WHITE = (220, 240, 255, 125)
PREVIEW_FILL = (180, 220, 255, 40)

# ==========================================
# CAMERA AND GRID
# ==========================================

GRID_SIZE = 40

camera_x = 0.0
camera_y = 0.0
CAMERA_SPEED = 300

zoom = 1.0
MIN_ZOOM = 0.25
MAX_ZOOM = 4.0
ZOOM_FACTOR = 1.1

# ==========================================
# CIRCUIT AND EDITOR
# ==========================================

circuit = Circuit()

selected_tool = "wire"
placement_rotation = 0
wire_start = None

selected_objects = set()

selecting = False
selection_start = None
selection_end = None

DRAG_THRESHOLD = 5

game_state = "menu"

# ==========================================
# COORDINATES
# ==========================================

def mouse_to_grid():
    mx, my = pygame.mouse.get_pos()

    wx = (mx - camera_x) / zoom
    wy = (my - camera_y) / zoom

    return (
        round(wx / GRID_SIZE) * GRID_SIZE,
        round(wy / GRID_SIZE) * GRID_SIZE
    )


def to_screen(position):
    x, y = position

    return (
        round(x * zoom + camera_x),
        round(y * zoom + camera_y)
    )


def make_rect(a, b):
    return pygame.Rect(
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(1, abs(a[0] - b[0])),
        max(1, abs(a[1] - b[1]))
    )


def lever_rect(lever):
    x, y = to_screen(lever.position)
    radius = max(4, round(12 * zoom))

    return pygame.Rect(
        x - radius, y - radius,
        radius * 2, radius * 2
    )


def gate_rect(gate):
    x, y = gate.position

    return make_rect(
        to_screen((x - 45, y - 45)),
        to_screen((x + 45, y + 45))
    )


def all_gates():
    return circuit.not_gates + circuit.and_gates


# ==========================================
# SELECTION GEOMETRY
# ==========================================

def distance_to_wire(point, wire):
    px, py = point
    ax, ay = to_screen(wire.start)
    bx, by = to_screen(wire.end)

    dx = bx - ax
    dy = by - ay

    length = dx * dx + dy * dy

    if length == 0:
        return float("inf")

    t = (
        (px - ax) * dx +
        (py - ay) * dy
    ) / length

    t = max(0, min(1, t))

    cx = ax + t * dx
    cy = ay + t * dy

    return math.hypot(px - cx, py - cy)


def find_object_at(position):
    for gate in reversed(all_gates()):
        if gate_rect(gate).collidepoint(position):
            return gate

    for lever in reversed(circuit.levers):
        if lever_rect(lever).collidepoint(position):
            return lever

    for wire in reversed(circuit.wires):
        if distance_to_wire(
            position, wire
        ) <= max(6, 5 * zoom):
            return wire

    return None


def objects_in_rect(rect):
    found = set()

    for gate in all_gates():
        if rect.colliderect(gate_rect(gate)):
            found.add(gate)

    for lever in circuit.levers:
        if rect.colliderect(lever_rect(lever)):
            found.add(lever)

    for wire in circuit.wires:
        if rect.clipline(
            to_screen(wire.start),
            to_screen(wire.end)
        ):
            found.add(wire)

    return found


def finish_selection(position, add=False):
    global selecting

    if not selecting:
        return

    distance = math.dist(
        selection_start, position
    )

    if distance < DRAG_THRESHOLD:
        obj = find_object_at(position)
        found = {obj} if obj is not None else set()
    else:
        found = objects_in_rect(
            make_rect(selection_start, position)
        )

    if not add:
        selected_objects.clear()

    selected_objects.update(found)
    selecting = False


def delete_selected():
    circuit.wires = [
        w for w in circuit.wires
        if w not in selected_objects
    ]

    circuit.levers = [
        l for l in circuit.levers
        if l not in selected_objects
    ]

    circuit.not_gates = [
        g for g in circuit.not_gates
        if g not in selected_objects
    ]

    circuit.and_gates = [
        g for g in circuit.and_gates
        if g not in selected_objects
    ]

    selected_objects.clear()
    circuit.rebuild()


# ==========================================
# DRAW HELPERS
# ==========================================

def draw_line(surface, color, a, b, width=3):
    pygame.draw.line(
        surface,
        color,
        to_screen(a),
        to_screen(b),
        max(1, round(width * zoom))
    )


def draw_dot(surface, position, color, radius=4):
    pygame.draw.circle(
        surface,
        color,
        to_screen(position),
        max(2, round(radius * zoom))
    )


def draw_tint(rect):
    overlay = pygame.Surface(
        (rect.width, rect.height),
        pygame.SRCALPHA
    )

    overlay.fill((255, 65, 65, 55))
    screen.blit(overlay, rect.topleft)


# ==========================================
# GRID
# ==========================================

def draw_grid():
    scaled = GRID_SIZE * zoom

    x = camera_x % scaled

    while x < WIDTH:
        pygame.draw.line(
            screen, GRID_COLOR,
            (round(x), 0),
            (round(x), HEIGHT)
        )
        x += scaled

    y = camera_y % scaled

    while y < HEIGHT:
        pygame.draw.line(
            screen, GRID_COLOR,
            (0, round(y)),
            (WIDTH, round(y))
        )
        y += scaled


# ==========================================
# LEVER DRAWING
# ==========================================

def draw_lever(lever, surface=screen, preview=False):
    selected = (
        not preview and lever in selected_objects
    )

    if preview:
        color = PREVIEW_WHITE
    elif selected:
        color = SELECT_RED
    else:
        color = WIRE_ON if lever.on else LEVER_OFF

    pygame.draw.circle(
        surface,
        color,
        to_screen(lever.position),
        max(2, round(12 * zoom))
    )

    if selected:
        pygame.draw.circle(
            surface, SELECT_RED,
            to_screen(lever.position),
            max(3, round(16 * zoom)),
            max(2, round(3 * zoom))
        )


# ==========================================
# NOT GATE DRAWING
# ==========================================

def draw_not_gate(gate, surface=screen, preview=False):
    selected = (
        not preview and gate in selected_objects
    )

    outline = (
        PREVIEW_WHITE if preview
        else SELECT_RED if selected
        else WHITE
    )

    fill = PREVIEW_FILL if preview else GATE_FILL

    # All shapes rotate with the terminals
    triangle = [
        to_screen(gate.point((-20, -20))),
        to_screen(gate.point((-20, 20))),
        to_screen(gate.point((12, 0)))
    ]

    pygame.draw.polygon(surface, fill, triangle)

    pygame.draw.polygon(
        surface, outline, triangle,
        max(1, round(2 * zoom))
    )

    pygame.draw.circle(
        surface, outline,
        to_screen(gate.point((18, 0))),
        max(2, round(6 * zoom)),
        max(1, round(2 * zoom))
    )

    if preview or selected:
        input_color = outline
        output_color = outline
    else:
        input_color = WIRE_ON if gate.input else WIRE_OFF
        output_color = WIRE_ON if gate.output else WIRE_OFF

    draw_line(
        surface, input_color,
        gate.input_position,
        gate.point((-20, 0))
    )

    draw_line(
        surface, output_color,
        gate.point((24, 0)),
        gate.output_position
    )

    draw_dot(
        surface, gate.input_position, input_color
    )

    draw_dot(
        surface, gate.output_position, output_color
    )

    if selected:
        draw_tint(gate_rect(gate))
        pygame.draw.rect(
            screen, SELECT_RED, gate_rect(gate), 2
        )


# ==========================================
# AND GATE DRAWING
# ==========================================

def draw_and_gate(gate, surface=screen, preview=False):
    selected = (
        not preview and gate in selected_objects
    )

    outline = (
        PREVIEW_WHITE if preview
        else SELECT_RED if selected
        else WHITE
    )

    fill = PREVIEW_FILL if preview else GATE_FILL

    # D-shaped gate using a semicircle
    body = [
        (-22, -26),
        (-4, -26)
    ]

    for i in range(17):
        angle = -math.pi / 2 + i * math.pi / 16

        body.append((
            -4 + 26 * math.cos(angle),
            26 * math.sin(angle)
        ))

    body.append((-22, 26))

    points = [
        to_screen(gate.point(p)) for p in body
    ]

    pygame.draw.polygon(surface, fill, points)

    pygame.draw.polygon(
        surface, outline, points,
        max(1, round(2 * zoom))
    )

    if preview or selected:
        color_a = outline
        color_b = outline
        color_out = outline
    else:
        color_a = WIRE_ON if gate.input_a else WIRE_OFF
        color_b = WIRE_ON if gate.input_b else WIRE_OFF
        color_out = WIRE_ON if gate.output else WIRE_OFF

    draw_line(
        surface, color_a,
        gate.input_a_position,
        gate.point((-22, -12))
    )

    draw_line(
        surface, color_b,
        gate.input_b_position,
        gate.point((-22, 12))
    )

    draw_line(
        surface, color_out,
        gate.point((22, 0)),
        gate.output_position
    )

    draw_dot(
        surface, gate.input_a_position, color_a
    )

    draw_dot(
        surface, gate.input_b_position, color_b
    )

    draw_dot(
        surface, gate.output_position, color_out
    )

    if selected:
        draw_tint(gate_rect(gate))
        pygame.draw.rect(
            screen, SELECT_RED, gate_rect(gate), 2
        )


# ==========================================
# ALL CIRCUIT COMPONENTS
# ==========================================

def draw_components():
    for wire in circuit.wires:
        selected = wire in selected_objects

        color = (
            SELECT_RED if selected
            else WIRE_ON if wire.on
            else WIRE_OFF
        )

        draw_line(
            screen, color,
            wire.start, wire.end,
            6 if selected else 4
        )

    for lever in circuit.levers:
        draw_lever(lever)

    for gate in circuit.not_gates:
        draw_not_gate(gate)

    for gate in circuit.and_gates:
        draw_and_gate(gate)


# ==========================================
# PLACEMENT PREVIEW
# ==========================================

def draw_placement_preview():
    if selected_tool == "select":
        return

    position = mouse_to_grid()

    # Transparent overlay for all previews
    overlay = pygame.Surface(
        (WIDTH, HEIGHT),
        pygame.SRCALPHA
    )

    if selected_tool == "wire":
        if wire_start is None:
            # Show where the wire will start
            draw_dot(
                overlay, position,
                PREVIEW_WHITE, 6
            )
        else:
            points = route_wire(
                wire_start, position
            )

            for i in range(len(points) - 1):
                draw_line(
                    overlay, PREVIEW_WHITE,
                    points[i], points[i + 1], 3
                )

    elif selected_tool == "lever":
        preview = Lever(position)
        draw_lever(preview, overlay, True)

    elif selected_tool == "not":
        preview = NotGate(
            position, placement_rotation
        )
        draw_not_gate(preview, overlay, True)

    elif selected_tool == "and":
        preview = AndGate(
            position, placement_rotation
        )
        draw_and_gate(preview, overlay, True)

    screen.blit(overlay, (0, 0))


# ==========================================
# SELECTION BOX
# ==========================================

def draw_selection():
    if not selecting:
        return

    rect = make_rect(
        selection_start, selection_end
    )

    draw_tint(rect)

    pygame.draw.rect(
        screen, SELECT_RED, rect, 2
    )


# ==========================================
# PLACE COMPONENT
# ==========================================

def handle_left_click():
    global wire_start

    position = mouse_to_grid()

    if selected_tool == "wire":
        if wire_start is None:
            wire_start = position
        else:
            points = route_wire(
                wire_start, position
            )

            for i in range(len(points) - 1):
                circuit.add_wire(
                    points[i], points[i + 1]
                )

            wire_start = None

    elif selected_tool == "lever":
        if not circuit.toggle_lever(position):
            circuit.add_lever(position)

    elif selected_tool == "not":
        circuit.add_not_gate(
            position, placement_rotation
        )

    elif selected_tool == "and":
        circuit.add_and_gate(
            position, placement_rotation
        )


# ==========================================
# MAIN MENU
# ==========================================

play_button = pygame.Rect(380, 320, 240, 60)
quit_button = pygame.Rect(380, 405, 240, 60)


def draw_button(rect, label):
    hovered = rect.collidepoint(
        pygame.mouse.get_pos()
    )

    color = (
        (55, 120, 185) if hovered
        else (30, 85, 145)
    )

    pygame.draw.rect(
        screen, color, rect, border_radius=8
    )

    pygame.draw.rect(
        screen, WHITE, rect, 2, border_radius=8
    )

    text = font.render(label, True, WHITE)

    screen.blit(
        text,
        text.get_rect(center=rect.center)
    )


def draw_menu():
    screen.fill(BACKGROUND)

    for x in range(0, WIDTH, GRID_SIZE):
        pygame.draw.line(
            screen, GRID_COLOR,
            (x, 0), (x, HEIGHT)
        )

    for y in range(0, HEIGHT, GRID_SIZE):
        pygame.draw.line(
            screen, GRID_COLOR,
            (0, y), (WIDTH, y)
        )

    title = title_font.render(
        "LOGIC GATE SANDBOX", True, WHITE
    )

    screen.blit(
        title,
        title.get_rect(center=(WIDTH // 2, 190))
    )

    subtitle = font.render(
        "Build. Connect. Experiment.",
        True, (185, 220, 245)
    )

    screen.blit(
        subtitle,
        subtitle.get_rect(center=(WIDTH // 2, 245))
    )

    draw_button(play_button, "PLAY")
    draw_button(quit_button, "QUIT")

    version = small_font.render(
        "Alpha 0.2", True, (185, 220, 245)
    )

    screen.blit(version, (20, HEIGHT - 30))


# ==========================================
# MAIN LOOP
# ==========================================

running = True

while running:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        elif game_state == "menu":

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:

                    if play_button.collidepoint(event.pos):
                        game_state = "playing"

                    elif quit_button.collidepoint(event.pos):
                        running = False

        elif game_state == "playing":

            if event.type == pygame.KEYDOWN:

                tool_keys = {
                    pygame.K_1: "wire",
                    pygame.K_2: "lever",
                    pygame.K_3: "not",
                    pygame.K_4: "and",
                    pygame.K_x: "select"
                }

                if event.key in tool_keys:
                    selected_tool = tool_keys[event.key]
                    placement_rotation = 0
                    wire_start = None
                    selecting = False
                    selected_objects.clear()

                # Rotate placement preview
                elif event.key == pygame.K_r:

                    if selected_tool in ("not", "and"):

                        if event.mod & pygame.KMOD_SHIFT:
                            # Clockwise
                            placement_rotation = (
                                placement_rotation - 1
                            ) % 4

                        else:
                            # Counterclockwise
                            placement_rotation = (
                                placement_rotation + 1
                            ) % 4

                elif event.key == pygame.K_BACKSPACE:
                    if selected_tool == "select":
                        delete_selected()

                elif event.key == pygame.K_ESCAPE:
                    wire_start = None
                    selecting = False
                    selected_objects.clear()
                    game_state = "menu"

            elif event.type == pygame.MOUSEWHEEL:
                mx, my = pygame.mouse.get_pos()

                old_zoom = zoom
                zoom *= ZOOM_FACTOR ** event.y
                zoom = max(
                    MIN_ZOOM,
                    min(MAX_ZOOM, zoom)
                )

                scale = zoom / old_zoom

                camera_x = (
                    mx - (mx - camera_x) * scale
                )
                camera_y = (
                    my - (my - camera_y) * scale
                )

            elif event.type == pygame.MOUSEBUTTONDOWN:

                if event.button == 1:
                    if selected_tool == "select":
                        selecting = True
                        selection_start = event.pos
                        selection_end = event.pos
                    else:
                        handle_left_click()

                elif event.button == 3:
                    wire_start = None

            elif event.type == pygame.MOUSEMOTION:
                if selecting:
                    selection_end = event.pos

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and selecting:

                    shift_held = bool(
                        pygame.key.get_mods()
                        & pygame.KMOD_SHIFT
                    )

                    finish_selection(
                        event.pos, add=shift_held
                    )

    # ======================================
    # DRAW
    # ======================================

    if game_state == "menu":
        draw_menu()

    elif game_state == "playing":

        keys = pygame.key.get_pressed()
        movement = CAMERA_SPEED * dt

        if keys[pygame.K_w]:
            camera_y += movement
        if keys[pygame.K_s]:
            camera_y -= movement
        if keys[pygame.K_a]:
            camera_x += movement
        if keys[pygame.K_d]:
            camera_x -= movement

        screen.fill(BACKGROUND)

        draw_grid()
        draw_components()
        draw_placement_preview()
        draw_selection()

    pygame.display.flip()

pygame.quit()
