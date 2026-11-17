
"""Interface drawing and hitboxes. Controls stay in main.py."""
import math
import pygame

TOOLS = (
    'wire', 'lever', 'button', 'not', 'and',
    'or', 'xor', 'nor', 'nand', 'light', 'delayer', 'junction',
    'capacitor',
    'transistor'
)

DEFAULT_SLOTS = {
    1: 'wire',
    2: 'lever',
    3: 'not',
    4: 'and',
    5: 'or',
    6: 'xor',
    7: 'nor',
    8: 'nand',
    9: 'light'
}


class GameUI:
    MODES = ('edit', 'view', 'render')

    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.font = pygame.font.SysFont(
            'consolas', 16, bold=True
        )
        self.small = pygame.font.SysFont(
            'consolas', 12, bold=True
        )
        self.title = pygame.font.SysFont(
            'consolas', 27, bold=True
        )

        self.inventory_scroll = 0
        self.view_mode = 'edit'
        self.from_rect = self.edit_mode_rect()
        self.transition_start = -10000

    @property
    def pause_rect(self):
        return pygame.Rect(16, 16, 56, 42)

    @property
    def inventory_rect(self):
        return pygame.Rect(
            self.width - 104, 16, 88, 42
        )

    @property
    def resume_rect(self):
        return pygame.Rect(
            self.width // 2 - 130,
            self.height // 2, 260, 50
        )

    @property
    def menu_rect(self):
        return pygame.Rect(
            self.width // 2 - 130,
            self.height // 2 + 62, 260, 50
        )

    def toolbar_rects(self):
        slotw = 49
        gap = 4
        centerw = 76
        actionw = 65

        total = (
            9 * slotw + centerw + actionw + 11 * gap
        )

        x = (self.width - total) // 2
        y = self.height - 84
        slots = {}

        for number in range(1, 5):
            slots[number] = pygame.Rect(
                x, y + 8, slotw, 58
            )
            x += slotw + gap

        center = pygame.Rect(
            x, y, centerw, centerw
        )
        x += centerw + gap

        for number in range(5, 10):
            slots[number] = pygame.Rect(
                x, y + 8, slotw, 58
            )
            x += slotw + gap

        select = pygame.Rect(
            x, y + 8, actionw, 28
        )
        mode = pygame.Rect(
            x, y + 40, actionw, 26
        )

        return slots, center, select, mode

    def edit_mode_rect(self):
        return self.toolbar_rects()[3]

    def compact_mode_rect(self):
        return pygame.Rect(
            self.width - 114,
            self.height - 72, 94, 48
        )

    def mode_rect(self):
        end = (
            self.edit_mode_rect()
            if self.view_mode == 'edit'
            else self.compact_mode_rect()
        )

        t = max(
            0, min(
                1,
                (pygame.time.get_ticks() -
                 self.transition_start) / 600
            )
        )
        t = t * t * (3 - 2 * t)

        a = self.from_rect

        return pygame.Rect(
            round(a.x + (end.x - a.x) * t),
            round(a.y + (end.y - a.y) * t),
            round(a.w + (end.w - a.w) * t),
            round(a.h + (end.h - a.h) * t)
        )

    def set_mode(self, mode):
        if mode != self.view_mode:
            self.from_rect = self.mode_rect()
            self.transition_start = pygame.time.get_ticks()
            self.view_mode = mode

    def panel(self, screen, rect, active=False, alpha=205):
        layer = pygame.Surface(
            rect.size, pygame.SRCALPHA
        )

        pygame.draw.rect(
            layer,
            (52, 84, 123, alpha) if active
            else (24, 43, 66, alpha),
            layer.get_rect(),
            border_radius=6
        )
        pygame.draw.rect(
            layer,
            (250, 216, 110, 235) if active
            else (174, 197, 222, 220),
            layer.get_rect(), 2,
            border_radius=6
        )
        screen.blit(layer, rect.topleft)

    def text(self, screen, words, center,
             font=None, color=(245, 249, 255)):
        image = (
            font or self.small
        ).render(str(words), True, color)

        screen.blit(
            image, image.get_rect(center=center)
        )

    def symbol(self, screen, tool, center, scale=1):
        cx, cy = center
        color = (236, 243, 253)

        def pt(x, y):
            return (
                round(cx + x * scale),
                round(cy + y * scale)
            )

        def lines(points, line_color=color):
            pygame.draw.lines(
                screen, line_color, False,
                [pt(*p) for p in points],
                max(1, round(2 * scale))
            )

        if tool == 'wire':
            lines(
                [(-12, 10), (-3, 10),
                 (6, -10), (12, -10)],
                (75, 221, 129)
            )

        elif tool == 'junction':
            pygame.draw.circle(
                screen, (240, 65, 75),
                center, max(3, round(7 * scale))
            )
            pygame.draw.circle(
                screen, color,
                center, max(3, round(7 * scale)),
                max(1, round(scale))
            )

        elif tool == 'transistor':
            pygame.draw.circle(
                screen, color, center,
                max(5, round(11 * scale)),
                max(1, round(2 * scale))
            )
            lines([(-17, 0), (-11, 0)])
            lines([(11, 0), (17, 0)])
            lines([(0, -17), (0, -11)])
            lines([(0, -7), (0, 7)],
                  (245, 178, 100))

        elif tool == 'capacitor':
            pygame.draw.rect(
                screen, color,
                pygame.Rect(
                    pt(-10, -13),
                    (round(20 * scale), round(26 * scale))
                ),
                max(1, round(2 * scale))
            )
            lines([(0, -18), (0, -13)])
            lines([(0, 13), (0, 18)])

            pygame.draw.line(
                screen, (75, 221, 129),
                pt(-7, 4), pt(7, 4),
                max(1, round(3 * scale))
            )

        elif tool == 'lever':
            pygame.draw.circle(
                screen, color, center,
                max(2, round(11 * scale)), 2
            )
            lines(
                [(0, 7), (7, -9)],
                (75, 221, 129)
            )

        elif tool == 'button':
            pygame.draw.rect(
                screen, color,
                pygame.Rect(
                    pt(-12, -12),
                    (round(24 * scale), round(24 * scale))
                ), 2
            )
            pygame.draw.circle(
                screen, (75, 221, 129), center,
                max(2, round(8 * scale))
            )

        elif tool == 'light':
            pygame.draw.rect(
                screen, color,
                pygame.Rect(
                    pt(-12, -12),
                    (round(24 * scale), round(24 * scale))
                ), 2
            )
            pygame.draw.circle(
                screen, (255, 230, 125), center,
                max(2, round(8 * scale))
            )

        elif tool in ('not', 'delayer'):
            pygame.draw.polygon(
                screen, color,
                [
                    pt(-13, -12),
                    pt(13, 0),
                    pt(-13, 12)
                ], 2
            )

            if tool == 'not':
                pygame.draw.circle(
                    screen, color, pt(16, 0),
                    max(2, round(3 * scale)), 2
                )
            else:
                pygame.draw.line(
                    screen, (75, 221, 129),
                    pt(-9, -4), pt(-9, 4),
                    max(1, round(3 * scale))
                )

        elif tool == 'select':
            pygame.draw.polygon(
                screen, color,
                [
                    pt(-9, -12), pt(-9, 12),
                    pt(-3, 5), pt(5, 11),
                    pt(9, 8), pt(1, 0),
                    pt(12, -2)
                ]
            )


        else:
            # Proper curved gate icons.

            def curve(a, control, b, steps=20):
                points = []

                for i in range(steps + 1):
                    t = i / steps
                    u = 1 - t

                    points.append((
                        u*u*a[0] + 2*u*t*control[0] + t*t*b[0],
                        u*u*a[1] + 2*u*t*control[1] + t*t*b[1]
                    ))

                return points

            if tool in ('and', 'nand'):
                # D-shaped AND / NAND.
                body = [(-12, -12), (-2, -12)]

                for i in range(21):
                    angle = -math.pi / 2 + math.pi * i / 20
                    body.append((
                        -2 + 12 * math.cos(angle),
                        12 * math.sin(angle)
                    ))

                body.append((-12, 12))

            else:
                # Smooth OR / XOR / NOR.
                top = curve(
                    (-12, -12), (4, -15), (13, 0)
                )
                bottom = curve(
                    (13, 0), (4, 15), (-12, 12)
                )
                back = curve(
                    (-12, 12), (-4, 0), (-12, -12)
                )

                body = top + bottom[1:] + back[1:]

            pygame.draw.lines(
                screen, color, True,
                [pt(x, y) for x, y in body],
                max(1, round(2 * scale))
            )

            if tool == 'xor':
                extra = curve(
                    (-16, -12), (-8, 0), (-16, 12)
                )
                pygame.draw.lines(
                    screen, color, False,
                    [pt(x, y) for x, y in extra],
                    max(1, round(2 * scale))
                )

            if tool in ('nand', 'nor'):
                pygame.draw.circle(
                    screen, color, pt(16, 0),
                    max(2, round(3 * scale)),
                    max(1, round(2 * scale))
                )


    def scroll_inventory(self, rows):
        max_scroll = max(
            0, (len(TOOLS) + 1) // 2 - 4
        )
        self.inventory_scroll = max(
            0,
            min(
                max_scroll,
                self.inventory_scroll + rows
            )
        )

    def inventory_cards(self):
        cards = []

        start = self.inventory_scroll * 2
        visible = TOOLS[start:start + 8]

        for i, tool in enumerate(visible):
            rect = pygame.Rect(
                self.width // 2 - 350
                + (i % 2) * 358,
                135 + (i // 2) * 100,
                340, 80
            )

            star = pygame.Rect(
                rect.right - 50,
                rect.y + 20,
                40, 40
            )

            cards.append((tool, rect, star))

        return cards

    def star(self, screen, center, slot):
        points = []

        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            radius = 17 if i % 2 == 0 else 8

            points.append((
                round(center[0] + radius * math.cos(a)),
                round(center[1] + radius * math.sin(a))
            ))

        pygame.draw.polygon(
            screen,
            (255, 218, 92) if slot
            else (124, 139, 157),
            points
        )

        if slot:
            self.text(
                screen, str(slot), center,
                self.small, (35, 40, 47)
            )

    def draw_inventory(self, screen, selected, favorites):
        veil = pygame.Surface(
            (self.width, self.height),
            pygame.SRCALPHA
        )
        veil.fill((5, 9, 18, 230))
        screen.blit(veil, (0, 0))

        background = pygame.Rect(
            self.width // 2 - 380,
            65, 760, 560
        )

        pygame.draw.rect(
            screen, (26, 37, 53),
            background, border_radius=12
        )
        pygame.draw.rect(
            screen, (135, 155, 180),
            background, 2, border_radius=12
        )

        self.text(
            screen, 'COMPONENT INVENTORY',
            (self.width // 2, 93), self.title
        )

        for tool, rect, star in self.inventory_cards():
            pygame.draw.rect(
                screen,
                (55, 80, 105) if selected == tool
                else (37, 49, 67),
                rect, border_radius=8
            )
            pygame.draw.rect(
                screen,
                (250, 216, 110) if selected == tool
                else (100, 118, 139),
                rect, 2, border_radius=8
            )

            self.symbol(
                screen, tool,
                (rect.x + 34, rect.centery), 1.1
            )
            self.text(
                screen, tool.upper(),
                (rect.x + 135, rect.centery), self.font
            )
            self.star(
                screen, star.center, favorites.get(tool)
            )

        self.text(
            screen,
            'Mouse wheel: scroll | Star: hotbar | Alt/Esc closes',
            (self.width // 2, 597)
        )

    def draw_pause(self, screen):
        veil = pygame.Surface(
            (self.width, self.height),
            pygame.SRCALPHA
        )
        veil.fill((6, 10, 18, 225))
        screen.blit(veil, (0, 0))

        self.text(
            screen, 'PAUSED',
            (self.width // 2, self.height // 2 - 65),
            self.title
        )

        for rect, label in (
            (self.resume_rect, 'RESUME'),
            (self.menu_rect, 'MAIN MENU')
        ):
            self.panel(screen, rect, alpha=245)
            self.text(
                screen, label, rect.center, self.font
            )

    def draw(self, screen, selected, hotbar, favorites,
             inventory_open=False, paused=False):
        self.panel(
            screen, self.pause_rect,
            alpha=240 if self.view_mode != 'edit' else 185
        )

        x, y = self.pause_rect.center
        for dx in (-7, 7):
            pygame.draw.rect(
                screen, (245, 250, 255),
                (x + dx - 3, y - 11, 6, 22),
                border_radius=1
            )

        if self.view_mode == 'edit':
            self.panel(screen, self.inventory_rect)
            self.text(
                screen, 'ALT',
                self.inventory_rect.center, self.font
            )

            rects, center, select, _ = self.toolbar_rects()

            for num, rect in rects.items():
                tool = hotbar[num]

                self.panel(
                    screen, rect,
                    active=(tool == selected)
                )
                self.symbol(
                    screen, tool,
                    (rect.centerx, rect.centery - 6), 0.9
                )
                self.text(
                    screen, num,
                    (rect.centerx, rect.bottom - 10)
                )

            pygame.draw.circle(
                screen, (25, 48, 76),
                center.center, 35
            )
            pygame.draw.circle(
                screen, (205, 227, 247),
                center.center, 35, 3
            )

            self.symbol(
                screen, selected, center.center, 1.7
            )
            self.panel(
                screen, select,
                active=selected == 'select'
            )
            self.text(
                screen, 'X', select.center, self.font
            )

        mode_rect = self.mode_rect()

        self.panel(
            screen, mode_rect,
            alpha=245 if self.view_mode != 'edit'
            else 190
        )
        self.text(
            screen, self.view_mode.upper(),
            mode_rect.center,
            self.small if self.view_mode == 'render'
            else self.font
        )

        if inventory_open and self.view_mode == 'edit':
            self.draw_inventory(
                screen, selected, favorites
            )

        if paused:
            self.draw_pause(screen)

    def hit_main(self, position):
        if self.pause_rect.collidepoint(position):
            return 'pause', None

        if self.mode_rect().collidepoint(position):
            return 'mode', None

        if self.view_mode != 'edit':
            return None, None

        if self.inventory_rect.collidepoint(position):
            return 'inventory', None

        slots, center, select, _ = self.toolbar_rects()

        if select.collidepoint(position):
            return 'select', None

        if center.collidepoint(position):
            return 'center', None

        for number, rect in slots.items():
            if rect.collidepoint(position):
                return 'slot', number

        return None, None

    def hit_inventory(self, position):
        for tool, card, star in self.inventory_cards():
            if star.collidepoint(position):
                return 'star', tool
            if card.collidepoint(position):
                return 'tool', tool

        return None, None

    def hit_pause(self, position):
        if self.resume_rect.collidepoint(position):
            return 'resume'

        if self.menu_rect.collidepoint(position):
            return 'menu'

        return None
