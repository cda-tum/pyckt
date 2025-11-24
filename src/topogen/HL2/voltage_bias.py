subcircuits_pmos_vb = [
    {
        "name": "VoltageBias[p, 1]",
        # "name": "VoltageBiasP1",
        "type": "PMOS",
        "connections": {"drain": "in", "gate": "out", "source": "source"},
        "ports": ["in", "out", "source"],
    },
    {
        "name": "VoltageBias[p, 2]",
        # "name": "VoltageBiasP1",
        "type": "DIODE_PMOS",
        "connections": {"drain": "in", "gate": "out", "source": "source"},
        "ports": ["in", "out", "source"],
    },
    {
        "name": "VoltageBias[p, 3]",
        # "name": "VoltageBiasP1",
        # "type": "DIODE_PMOS",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "DIODE_PMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "DIODE_PMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "outSource",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "VoltageBias[p, 4]",
        # "name": "VoltageBiasP1",
        # "type": "DIODE_PMOS",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "PMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "PMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "in",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "VoltageBias[p, 5]",
        # "name": "VoltageBiasP1",
        # "type": "DIODE_PMOS",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "DIODE_PMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "PMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "outSource",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "VoltageBias[p, 6]",
        # "name": "VoltageBiasP1",
        # "type": "DIODE_PMOS",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "DIODE_PMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "PMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "in",
                    "source": "source",
                },
            },
        ],
    },
]


subcircuits_nmos_vb = [
    {
        "name": "VoltageBias[n, 1]",
        "type": "NMOS",
        "connections": {"drain": "in", "gate": "out", "source": "source"},
        "ports": ["in", "out", "source"],
    },
    {
        "name": "VoltageBias[n, 2]",
        "type": "DIODE_NMOS",
        "connections": {"drain": "in", "gate": "out", "source": "source"},
        "ports": ["in", "out", "source"],
    },
    {
        "name": "VoltageBias[n, 3]",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "DIODE_NMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "DIODE_NMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "outSource",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "VoltageBias[n, 4]",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "NMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "NMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "in",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "VoltageBias[n, 5]",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "DIODE_NMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "NMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "outSource",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "VoltageBias[n, 6]",
        "ports": ["in", "inner", "outInput", "outSource", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "DIODE_NMOS",
                "connections": {"drain": "in", "gate": "outInput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "NMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "in",
                    "source": "source",
                },
            },
        ],
    },
]

subcircuit_vb = subcircuits_pmos_vb + subcircuits_nmos_vb
