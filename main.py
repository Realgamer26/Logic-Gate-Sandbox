
"""Logic Gate Sandbox Alpha 0.7.1. Run with: python main.py"""
import sys
import copy


def startup_error(details):
    print(
        'Logic Gate Sandbox startup error:',
        details, file=sys.stderr
    )

    try:
        from tkinter import Tk, messagebox
        root = Tk()
        root.withdraw()

        try:
            messagebox.showerror(
                'Logic Gate Sandbox', str(details)
            )
        finally:
            root.destroy()

    except Exception:
        pass


try:
    import math
    import pygame

    from logic import (
        Circuit, Lever, Button, Light,
        NotGate, AndGate, Delayer, Capacitor, Transistor,
        overlaps, wire_route, point_on_wire, GRID
    )
    from render import (
        draw_dark_mode, draw_lever, draw_push_button,
        draw_light, draw_gate, draw_capacitor, draw_transistor, GREEN, WHITE
    )
    from ui import GameUI, DEFAULT_SLOTS
    from savegame import save_circuit, load_circuit

except ImportError as e:
    startup_error(e)
    sys.exit(1)


pygame.init()

W, H = 1000, 700
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption(
    'Logic Gate Sandbox - Alpha 0.7.1'
)

clock = pygame.time.Clock()
font = pygame.font.SysFont('consolas', 24)
small = pygame.font.SysFont('consolas', 16)
ui = GameUI(W, H)

circuit = Circuit()

camera_x = 0.0
camera_y = 0.0
zoom = 1.0

selected_tool = 'wire'
rotation = 0
mode = 'edit'
scene = 'menu'
paused = False
inventory_open = False

wire_start = None
pressed_button = None
undo_stack = []
redo_stack = []
HISTORY_LIMIT = 100

selected_objects = set()
selection_start = None
selection_end = None

# New assignments take priority.
# Displaced assignments are remembered.
favorites = {}

message = ''
message_until = 0

KEYS = {
    getattr(pygame, 'K_' + str(i)): i
    for i in range(1, 10)
}
MODS = (
    pygame.KMOD_CTRL |
    pygame.KMOD_ALT |
    pygame.KMOD_SHIFT
)


# ==========================================
# HELPERS
# ==========================================

def remember():
    undo_stack.append(copy.deepcopy(circuit))
    if len(undo_stack) > HISTORY_LIMIT:
        undo_stack.pop(0)
    redo_stack.clear()


def undo():
    global circuit
    if not undo_stack:
        notify('Nothing to undo')
        return
    reset_edit_action()
    redo_stack.append(copy.deepcopy(circuit))
    circuit = undo_stack.pop()
    notify('Undo')


def redo():
    global circuit
    if not redo_stack:
        notify('Nothing to redo')
        return
    reset_edit_action()
    undo_stack.append(copy.deepcopy(circuit))
    circuit = redo_stack.pop()
    notify('Redo')


def notify(text):
    global message, message_until

    message = str(text)
    message_until = (
        pygame.time.get_ticks() + 2600
    )


def to_screen(pos):
    return (
        round(pos[0] * zoom + camera_x),
        round(pos[1] * zoom + camera_y)
    )


def grid_pos(pixel=None):
    x, y = (
        pixel if pixel is not None
        else pygame.mouse.get_pos()
    )

    return (
        round((x - camera_x) / zoom / GRID) * GRID,
        round((y - camera_y) / zoom / GRID) * GRID
    )


def hotbar():
    result = DEFAULT_SLOTS.copy()

    for item, slot in favorites.items():
        result[slot] = item

    return result


def cycle_favorite(item):
    old = favorites.pop(item, 0)

    if old < 9:
        favorites[item] = old + 1


def release_button():
    global pressed_button

    if pressed_button is not None:
        pressed_button.release()
        pressed_button = None
        circuit.update(0)


def reset_edit_action():
    global wire_start, selection_start, selection_end

    wire_start = None
    selection_start = None
    selection_end = None

    selected_objects.clear()
    release_button()


def choose(item):
    global selected_tool, rotation

    reset_edit_action()
    selected_tool = item
    rotation = 0


def mode_change(direction=1):
    global mode, inventory_open

    if paused:
        return

    reset_edit_action()
    inventory_open = False

    modes = ('edit', 'view', 'render')
    mode = modes[
        (modes.index(mode) + direction) % 3
    ]

    ui.set_mode(mode)


def pause_toggle():
    global paused, inventory_open

    if not paused:
        reset_edit_action()
        inventory_open = False

    paused = not paused


def save_game():
    try:
        save_circuit(
            circuit, camera_x, camera_y, zoom
        )
        notify('Saved circuit')

    except (OSError, ValueError, TypeError) as e:
        notify('Save error: ' + str(e))


def load_game():
    global circuit, camera_x, camera_y, zoom

    try:
        obj, x, y, z = load_circuit()

        if not all(
            math.isfinite(v) for v in (x, y, z)
        ):
            raise ValueError('Invalid camera')

        reset_edit_action()
        undo_stack.clear()
        redo_stack.clear()
        circuit = obj
        camera_x = x
        camera_y = y
        zoom = max(0.25, min(4, z))

        notify('Loaded circuit')
        return True

    except (
        OSError, ValueError, TypeError, KeyError
    ) as e:
        notify('Load error: ' + str(e))
        return False


def new_game():
    global circuit, camera_x, camera_y, zoom
    global scene, mode, paused, inventory_open

    reset_edit_action()
    undo_stack.clear()
    redo_stack.clear()
    circuit = Circuit()

    camera_x = 0
    camera_y = 0
    zoom = 1

    scene = 'playing'
    paused = False
    inventory_open = False
    mode = 'edit'

    ui.set_mode(mode)
    notify('New circuit')


# ==========================================
# SELECTION AND HITBOXES
# ==========================================

def component_rect(obj):
    from logic import footprint

    pts = [
        to_screen(q) for q in footprint(obj)
    ]

    return pygame.Rect(
        min(p[0] for p in pts),
        min(p[1] for p in pts),
        max(p[0] for p in pts) -
        min(p[0] for p in pts) + 1,
        max(p[1] for p in pts) -
        min(p[1] for p in pts) + 1
    )


def wire_hit(pixel, wire):
    x, y = pixel
    ax, ay = to_screen(wire.start)
    bx, by = to_screen(wire.end)

    dx = bx - ax
    dy = by - ay
    den = dx * dx + dy * dy

    if den:
        t = max(
            0, min(
                1,
                ((x - ax) * dx + (y - ay) * dy) / den
            )
        )
    else:
        t = 0

    distance = math.hypot(
        x - ax - t * dx,
        y - ay - t * dy
    )

    return distance <= max(6, 5 * zoom)


def find_component(pixel, kind=None):
    for obj in reversed(circuit.components()):
        if (
            kind is not None
            and not isinstance(obj, kind)
        ):
            continue

        if component_rect(obj).collidepoint(pixel):
            return obj

    return None


def start_button(pixel):
    global pressed_button

    button = find_component(pixel, Button)

    if button is not None:
        release_button()
        pressed_button = button
        button.press()
        circuit.update(0)
        return True

    return False


def click_operate(pixel):
    if start_button(pixel):
        return

    lever = find_component(pixel, Lever)

    if lever is not None:
        remember()
        lever.toggle()
        circuit.update(0)


def right_click(pixel):
    global wire_start

    if mode != 'edit':
        return

    gate = find_component(pixel, Delayer)

    if gate is not None:
        remember()
        gate.cycle()
        notify(
            f'Delayer: {gate.delay:.1f} seconds'
        )
    else:
        wire_start = None


def selected_candidate(pos):
    if selected_tool == 'lever':
        return Lever(pos)

    if selected_tool == 'button':
        return Button(pos)

    if selected_tool == 'light':
        return Light(pos)

    if selected_tool == 'not':
        return NotGate(pos, rotation)

    if selected_tool == 'delayer':
        return Delayer(pos, rotation)

    if selected_tool == 'capacitor':
        return Capacitor(pos, rotation)

    if selected_tool == 'transistor':
        return Transistor(pos, rotation)

    if selected_tool in (
        'and', 'or', 'xor', 'nand', 'nor'
    ):
        return AndGate(
            pos, rotation, selected_tool
        )

    return None


# ==========================================
# EDIT MODE DRAWING
# ==========================================

def draw_world():
    global selection_end

    screen.fill((27, 79, 145))
    span = GRID * zoom

    x = camera_x % span

    while x < W:
        pygame.draw.line(
            screen, (76, 124, 174),
            (round(x), 0), (round(x), H)
        )
        x += span

    y = camera_y % span

    while y < H:
        pygame.draw.line(
            screen, (76, 124, 174),
            (0, round(y)), (W, round(y))
        )
        y += span

    for wire in circuit.wires:
        color = (
            (248, 81, 85)
            if wire in selected_objects
            else GREEN if wire.on else WHITE
        )

        pygame.draw.line(
            screen, color,
            to_screen(wire.start),
            to_screen(wire.end),
            max(1, round(4 * zoom))
        )

    for junction in circuit.junctions:
        center = to_screen(junction.position)
        pygame.draw.circle(
            screen, (235, 65, 65),
            center, max(4, round(6 * zoom))
        )
        pygame.draw.circle(
            screen, WHITE,
            center, max(4, round(6 * zoom)), 1
        )

    for lever in circuit.levers:
        draw_lever(
            screen, to_screen(lever.position),
            zoom, lever.on
        )

    for button in circuit.buttons:
        draw_push_button(
            screen, to_screen(button.position),
            zoom, button.on
        )

    for light in circuit.lights:
        draw_light(
            screen, to_screen(light.position),
            zoom, light.on
        )

    for transistor in circuit.transistors:
        transistor._display_control = circuit.signal_at(
            transistor.control_position
        )
        draw_transistor(
            screen, transistor, to_screen, zoom
        )

    for capacitor in circuit.capacitors:
        draw_capacitor(
            screen, capacitor, to_screen, zoom
        )

    for gate in (
        circuit.not_gates +
        circuit.and_gates +
        circuit.delayers
    ):
        draw_gate(
            screen, gate,
            to_screen, zoom, circuit
        )

    for obj in selected_objects:
        if (
            hasattr(obj, 'position')
            and obj not in circuit.junctions
        ):
            pygame.draw.rect(
                screen, (255, 65, 65),
                component_rect(obj), 2
            )

    if (
        selection_start is not None
        and selection_end is not None
    ):
        rect = pygame.Rect(
            min(selection_start[0], selection_end[0]),
            min(selection_start[1], selection_end[1]),
            abs(
                selection_start[0] - selection_end[0]
            ),
            abs(
                selection_start[1] - selection_end[1]
            )
        )

        pygame.draw.rect(
            screen, (255, 65, 65), rect, 2
        )

    # Preview; red means placement is blocked.
    if not inventory_open and not paused:
        pos = grid_pos()

        if selected_tool == 'wire':
            if wire_start is not None:
                for a, b in wire_route(wire_start, pos):
                    pygame.draw.line(
                        screen, (200, 235, 255),
                        to_screen(a), to_screen(b), 2
                    )

        
        elif selected_tool == 'junction':
            pygame.draw.circle(
                screen, (255, 95, 95),
                to_screen(pos),
                max(4, round(6 * zoom)), 2
            )

        elif selected_tool != 'select':
            obj = selected_candidate(pos)

            if obj is not None:
                invalid = any(
                    overlaps(obj, existing)
                    for existing in circuit.components()
                )

                # Draw the actual component on a
                # transparent surface.
                preview = pygame.Surface(
                    (W, H), pygame.SRCALPHA
                )

                center = to_screen(obj.position)

                if isinstance(obj, Lever):
                    draw_lever(
                        preview, center, zoom, obj.on
                    )

                elif isinstance(obj, Button):
                    draw_push_button(
                        preview, center, zoom, obj.on
                    )

                elif isinstance(obj, Transistor):
                    obj._display_control = False
                    draw_transistor(
                        preview, obj, to_screen, zoom
                    )

                elif isinstance(obj, Capacitor):
                    draw_capacitor(
                        preview, obj, to_screen, zoom
                    )

                elif isinstance(obj, Light):
                    draw_light(
                        preview, center, zoom, obj.on
                    )

                else:
                    # Gates and Delayers use their
                    # real geometry and rotation.
                    draw_gate(
                        preview, obj,
                        to_screen, zoom, circuit
                    )

                # Make the component translucent.
                preview.set_alpha(150)
                screen.blit(preview, (0, 0))

                if invalid:
                    # A red overlay follows the exact
                    # component footprint.
                    from logic import footprint

                    points = [
                        to_screen(q)
                        for q in footprint(obj)
                    ]

                    warning = pygame.Surface(
                        (W, H), pygame.SRCALPHA
                    )

                    pygame.draw.polygon(
                        warning,
                        (255, 45, 55, 125),
                        points
                    )

                    pygame.draw.polygon(
                        warning,
                        (255, 55, 65, 255),
                        points, 3
                    )

                    screen.blit(warning, (0, 0))



# ==========================================
# PLACEMENT AND SELECTION
# ==========================================

def place(pixel):
    global wire_start

    pos = grid_pos(pixel)

    if selected_tool == 'wire':
        if wire_start is None:
            wire_start = pos
        else:
            # One drawing action = one wire group.
            remember()
            group_id = circuit.new_wire_group()

            for a, b in wire_route(wire_start, pos):
                circuit.add_wire(a, b, group_id)

            wire_start = None

        return

    if selected_tool == 'junction':
        if any(
            point_on_wire(pos, wire)
            for wire in circuit.wires
        ):
            remember()
            circuit.add_junction(pos)
        else:
            notify('Junction must touch a wire')
        return

    item = selected_candidate(pos)

    if item is not None:
        if any(
            overlaps(item, o)
            for o in circuit.components()
        ):
            notify(
                'Blocked: components cannot overlap'
            )
        else:
            remember()
            circuit.add(
                selected_tool, pos, rotation
            )


def select_finish(pixel, additive=False):
    global selection_start, selection_end

    if selection_start is None:
        return

    if not additive:
        selected_objects.clear()

    if math.dist(selection_start, pixel) < 5:
        obj = next(
            (
                junction
                for junction in reversed(circuit.junctions)
                if math.dist(
                    to_screen(junction.position), pixel
                ) <= max(8, 7 * zoom)
            ),
            None
        )

        if obj is None:
            obj = find_component(pixel)

        if obj:
            selected_objects.add(obj)

        else:
            for wire in circuit.wires:
                if wire_hit(pixel, wire):
                    selected_objects.add(wire)
                    break

    else:
        rect = pygame.Rect(
            min(selection_start[0], pixel[0]),
            min(selection_start[1], pixel[1]),
            abs(selection_start[0] - pixel[0]) + 1,
            abs(selection_start[1] - pixel[1]) + 1
        )

        for junction in circuit.junctions:
            if rect.collidepoint(
                to_screen(junction.position)
            ):
                selected_objects.add(junction)

        for obj in circuit.components():
            if rect.colliderect(
                component_rect(obj)
            ):
                selected_objects.add(obj)

        for wire in circuit.wires:
            if rect.clipline(
                to_screen(wire.start),
                to_screen(wire.end)
            ):
                selected_objects.add(wire)

    selection_start = None
    selection_end = None


# ==========================================
# MAIN MENU
# ==========================================

def menu_rect(i):
    return pygame.Rect(
        W // 2 - 125,
        270 + i * 85,
        250, 62
    )


def draw_menu():
    screen.fill((27, 79, 145))

    for x in range(0, W, GRID):
        pygame.draw.line(
            screen, (75, 125, 180),
            (x, 0), (x, H)
        )

    for y in range(0, H, GRID):
        pygame.draw.line(
            screen, (75, 125, 180),
            (0, y), (W, y)
        )

    headline = pygame.font.SysFont(
        'consolas', 42, bold=True
    ).render(
        'LOGIC GATE SANDBOX', True, WHITE
    )

    screen.blit(
        headline,
        headline.get_rect(center=(W // 2, 180))
    )

    for i, words in enumerate(
        ('PLAY', 'LOAD CIRCUIT', 'QUIT')
    ):
        r = menu_rect(i)

        pygame.draw.rect(
            screen, (40, 106, 166),
            r, border_radius=8
        )
        pygame.draw.rect(
            screen, WHITE, r, 2,
            border_radius=8
        )

        image = font.render(
            words, True, WHITE
        )

        screen.blit(
            image, image.get_rect(center=r.center)
        )

    version = small.render(
        'Alpha 0.7.1', True, WHITE
    )
    screen.blit(version, (20, H - 30))


# ==========================================
# GAME LOOP
# ==========================================

running = True

while running:
    dt = min(clock.tick(60) / 1000, 0.10)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            release_button()
            running = False
            continue

        if event.type == pygame.WINDOWFOCUSLOST:
            release_button()
            continue

        if (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
        ):
            release_button()

            if selection_start is not None:
                additive = bool(
                    pygame.key.get_mods()
                    & pygame.KMOD_SHIFT
                )
                select_finish(
                    event.pos, additive
                )

            continue

        if event.type == pygame.KEYDOWN:
            shortcut = bool(
                event.mod & (
                    pygame.KMOD_CTRL | pygame.KMOD_META
                )
            )

            if (
                shortcut
                and event.key == pygame.K_z
                and scene == 'playing'
                and not paused
            ):
                if event.mod & pygame.KMOD_SHIFT:
                    redo()
                else:
                    undo()
                continue

            ctrl = bool(
                event.mod & pygame.KMOD_CTRL
            )

            if ctrl and event.key in (
                pygame.K_s,
                pygame.K_l,
                pygame.K_n
            ):
                if event.key == pygame.K_s:
                    save_game()
                elif event.key == pygame.K_l:
                    load_game()
                else:
                    new_game()

                continue

        if scene == 'menu':
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                if menu_rect(0).collidepoint(event.pos):
                    scene = 'playing'

                elif menu_rect(1).collidepoint(event.pos):
                    if load_game():
                        scene = 'playing'

                elif menu_rect(2).collidepoint(event.pos):
                    running = False

            continue

        if paused:
            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_ESCAPE
            ):
                pause_toggle()

            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
            ):
                if (
                    ui.pause_rect.collidepoint(event.pos)
                    or ui.hit_pause(event.pos) == 'resume'
                ):
                    pause_toggle()

                elif ui.hit_pause(event.pos) == 'menu':
                    reset_edit_action()
                    paused = False
                    scene = 'menu'
                    inventory_open = False

            continue

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                direction = (
                    -1 if event.mod & pygame.KMOD_SHIFT
                    else 1
                )
                mode_change(direction)
                continue

            if event.key in (
                pygame.K_LALT, pygame.K_RALT
            ):
                if not getattr(event, 'repeat', False):
                    if mode == 'edit':
                        inventory_open = not inventory_open
                        reset_edit_action()
                continue

            if event.key == pygame.K_ESCAPE:
                if inventory_open:
                    inventory_open = False
                else:
                    pause_toggle()
                continue

            if inventory_open or mode != 'edit':
                continue

            if not (event.mod & MODS):
                if event.key in KEYS:
                    choose(
                        hotbar()[KEYS[event.key]]
                    )
                    continue

                if event.key == pygame.K_x:
                    choose('select')
                    continue

            if (
                event.key == pygame.K_r
                and not (
                    event.mod &
                    (pygame.KMOD_CTRL | pygame.KMOD_ALT)
                )
            ):
                if selected_tool in (
                    'not', 'and', 'or', 'xor',
                    'nand', 'nor', 'delayer',
                    'capacitor', 'transistor'
                ):
                    rotation = (
                        rotation +
                        (-1 if event.mod & pygame.KMOD_SHIFT
                         else 1)
                    ) % 4

            if (
                event.key in (
                    pygame.K_BACKSPACE, pygame.K_DELETE
                )
                and selected_tool == 'select'
            ):
                if selected_objects:
                    remember()
                circuit.remove(selected_objects)
                selected_objects.clear()

        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            if inventory_open:
                action, value = ui.hit_inventory(
                    event.pos
                )

                if action == 'star':
                    cycle_favorite(value)

                elif action == 'tool':
                    choose(value)
                    inventory_open = False

                continue

            action, value = ui.hit_main(event.pos)

            if action == 'pause':
                pause_toggle()

            elif action == 'mode':
                mode_change(1)

            elif action == 'inventory':
                inventory_open = True
                reset_edit_action()

            elif action == 'select':
                choose('select')

            elif action == 'slot':
                choose(hotbar()[value])

            elif action is not None:
                pass

            elif mode in ('view', 'render'):
                click_operate(event.pos)

            elif selected_tool == 'select':
                selection_start = event.pos
                selection_end = event.pos

            elif (
                not (
                    selected_tool == 'wire'
                    and wire_start is not None
                )
                and start_button(event.pos)
            ):
                # Buttons work with any selected tool
                # unless a wire is being drawn.
                pass

            else:
                place(event.pos)

        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 3
        ):
            right_click(event.pos)

        elif event.type == pygame.MOUSEWHEEL:
            if inventory_open:
                ui.scroll_inventory(-event.y)
            else:
                mx, my = pygame.mouse.get_pos()
                old = zoom

                zoom = max(
                    0.25,
                    min(4.0, zoom * (1.1 ** event.y))
                )

                ratio = zoom / old

                camera_x = (
                    mx - (mx - camera_x) * ratio
                )
                camera_y = (
                    my - (my - camera_y) * ratio
                )

        elif event.type == pygame.MOUSEMOTION:
            if selection_start is not None:
                selection_end = event.pos

    # --------------------------------------
    # Frame update and drawing
    # --------------------------------------

    if scene == 'menu':
        draw_menu()

    else:
        if not paused:
            circuit.update(dt)

        keys = pygame.key.get_pressed()

        modifier_lock = any((
            keys[pygame.K_LCTRL],
            keys[pygame.K_RCTRL],
            keys[pygame.K_LALT],
            keys[pygame.K_RALT],
            keys[pygame.K_LSHIFT],
            keys[pygame.K_RSHIFT]
        ))

        if (
            not paused
            and not inventory_open
            and not modifier_lock
        ):
            speed = 300 * dt

            camera_x += speed * (
                keys[pygame.K_a] - keys[pygame.K_d]
            )
            camera_y += speed * (
                keys[pygame.K_w] - keys[pygame.K_s]
            )

        if mode == 'edit':
            draw_world()
        else:
            draw_dark_mode(
                screen, circuit,
                to_screen, zoom,
                show_circuit=(mode == 'view')
            )

        ui.draw(
            screen,
            selected_tool,
            hotbar(),
            favorites,
            inventory_open,
            paused
        )

        if (
            message
            and pygame.time.get_ticks() < message_until
            and not inventory_open
            and not paused
        ):
            img = small.render(
                message, True, WHITE
            )

            p = img.get_rect(
                bottomleft=(20, H - 94)
            )

            pygame.draw.rect(
                screen, (26, 42, 62),
                p.inflate(16, 12),
                border_radius=4
            )
            screen.blit(img, p)

    pygame.display.flip()

release_button()
pygame.quit()
