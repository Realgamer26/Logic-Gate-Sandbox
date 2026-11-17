
"""JSON persistence, including older Alpha 0.6 saves."""
import json
import math
from pathlib import Path

from logic import (
    Circuit, Lever, Button, Light, Wire,
    NotGate, AndGate, Delayer, Capacitor, Junction
, Transistor)

SAVE_FILE = (
    Path.home() / 'Logic Gate Sandbox' /
    'saves' / 'circuit.json'
)


def save_circuit(circuit, camera_x, camera_y, zoom):
    SAVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = {
        'version': 2,
        'camera': {
            'x': camera_x,
            'y': camera_y,
            'zoom': zoom
        },
        'levers': [
            {'position': list(o.position), 'on': o.on}
            for o in circuit.levers
        ],
        'buttons': [
            {'position': list(o.position)}
            for o in circuit.buttons
        ],
        'lights': [
            {'position': list(o.position)}
            for o in circuit.lights
        ],
        'wires': [
            {
                'start': list(o.start),
                'end': list(o.end),
                'group_id': o.group_id
            }
            for o in circuit.wires
        ],
        'junctions': [
            {
                'position': list(o.position),
                'id': o.id
            }
            for o in circuit.junctions
        ],
        'next_junction_id': circuit.next_junction_id,
        'next_wire_group_id': circuit.next_wire_group_id,
        'transistors': [
            {
                'position': list(o.position),
                'rotation': o.rotation
            }
            for o in circuit.transistors
        ],
        'capacitors': [
            {
                'position': list(o.position),
                'rotation': o.rotation,
                'charge': o.charge
            }
            for o in circuit.capacitors
        ],
        'not_gates': [
            {'position': list(o.position), 'rotation': o.rotation}
            for o in circuit.not_gates
        ],
        'and_gates': [
            {
                'position': list(o.position),
                'rotation': o.rotation,
                'kind': o.kind
            }
            for o in circuit.and_gates
        ],
        'delayers': [
            {
                'position': list(o.position),
                'rotation': o.rotation,
                'delay_index': o.delay_index
            }
            for o in circuit.delayers
        ]
    }

    temporary = SAVE_FILE.with_suffix('.tmp')

    with temporary.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

    temporary.replace(SAVE_FILE)
    return SAVE_FILE


def load_circuit():
    with SAVE_FILE.open('r', encoding='utf-8') as f:
        data = json.load(f)

    if data.get('version') not in (None, 1, 2):
        raise ValueError('Unsupported save version')

    def p(v):
        if (
            not isinstance(v, (tuple, list))
            or len(v) != 2
            or not all(
                isinstance(x, (int, float)) and math.isfinite(x)
                for x in v
            )
        ):
            raise ValueError('Invalid component coordinates')

        return tuple(v)

    circuit = Circuit()

    for o in data.get('levers', []):
        v = Lever(p(o['position']))
        v.on = bool(o.get('on', False))
        circuit.levers.append(v)

    for o in data.get('buttons', []):
        circuit.buttons.append(Button(p(o['position'])))

    for o in data.get('lights', []):
        circuit.lights.append(Light(p(o['position'])))

    wire_data = data.get('wires', [])

    # For older saves, retain the original
    # endpoint-based connectivity.
    if data.get('version') in (None, 1):
        parent = {}

        def find(point):
            parent.setdefault(point, point)
            if parent[point] != point:
                parent[point] = find(parent[point])
            return parent[point]

        for entry in wire_data:
            a = p(entry['start'])
            b = p(entry['end'])
            parent[find(a)] = find(b)

        legacy_groups = {}
        for entry in wire_data:
            a = p(entry['start'])
            group = find(a)
            if group not in legacy_groups:
                legacy_groups[group] = len(legacy_groups) + 1

            circuit.wires.append(
                Wire(
                    a, p(entry['end']),
                    legacy_groups[group]
                )
            )
    else:
        for index, entry in enumerate(wire_data):
            group = entry.get('group_id')
            if group is None:
                group = index + 1

            circuit.wires.append(
                Wire(
                    p(entry['start']),
                    p(entry['end']),
                    int(group)
                )
            )

    circuit.next_wire_group_id = max(
        int(data.get('next_wire_group_id', 1)),
        max(
            (w.group_id for w in circuit.wires),
            default=0
        ) + 1
    )

    for entry in data.get('junctions', []):
        circuit.junctions.append(
            Junction(
                p(entry['position']),
                int(entry['id'])
            )
        )

    circuit.next_junction_id = max(
        int(data.get('next_junction_id', 10000)),
        max(
            (j.id for j in circuit.junctions),
            default=9999
        ) + 1
    )

    for o in data.get('transistors', []):
        circuit.transistors.append(
            Transistor(
                p(o['position']),
                int(o.get('rotation', 0))
            )
        )

    for o in data.get('capacitors', []):
        circuit.capacitors.append(
            Capacitor(
                p(o['position']),
                int(o.get('rotation', 0)),
                float(o.get('charge', 0.0))
            )
        )

    for o in data.get('not_gates', []):
        circuit.not_gates.append(
            NotGate(
                p(o['position']),
                int(o.get('rotation', 0))
            )
        )

    for o in data.get('and_gates', []):
        circuit.and_gates.append(
            AndGate(
                p(o['position']),
                int(o.get('rotation', 0)),
                o.get('kind', 'AND')
            )
        )

    for o in data.get('delayers', []):
        circuit.delayers.append(
            Delayer(
                p(o['position']),
                int(o.get('rotation', 0)),
                int(o.get('delay_index', 0))
            )
        )

    circuit.rebuild()
    cam = data.get('camera', {})

    return (
        circuit,
        float(cam.get('x', 0)),
        float(cam.get('y', 0)),
        float(cam.get('zoom', 1))
    )
