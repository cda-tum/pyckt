subcircuits_pmos_cb = [
    {
        "name": "CurrentBias[p, 1]",
        "type": "PMOS",
        "connections": {"drain": "in", "gate": "out", "source": "source"},
        "ports": ["in", "out", "source"],
    },
    {
        "name": "CurrentBias[p, 2]",
        "ports": ["out", "source", "inOutput", "inSource", "inner"],
        "instances": [
            {
                "name": "m1",
                "type": "PMOS",
                "connections": {"drain": "out", "gate": "inOutput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "PMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "inSource",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "CurrentBias[p, 3]",
        "ports": ["out", "source", "inOutput", "inSource", "inner"],
        "instances": [
            {
                "name": "m1",
                "type": "PMOS",
                "connections": {"drain": "out", "gate": "inOutput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "DIODE_PMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "inSource",
                    "source": "source",
                },
            },
        ],
    },
]


subcircuits_nmos_cb = [
    {
        "name": "CurrentBias[n, 1]",
        "type": "NMOS",
        "connections": {"drain": "out", "gate": "in", "source": "source"},
        "ports": ["in", "out", "source"],
    },
    {
        "name": "CurrentBias[n, 2]",
        "ports": ["out", "source", "inOutput", "inSource", "inner"],
        "instances": [
            {
                "name": "m1",
                "type": "NMOS",
                "connections": {"drain": "out", "gate": "inOutput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "NMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "inSource",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "CurrentBias[n, 3]",
        "ports": ["out", "source", "inOutput", "inSource", "inner"],
        "instances": [
            {
                "name": "m1",
                "type": "NMOS",
                "connections": {"drain": "out", "gate": "inOutput", "source": "inner"},
            },
            {
                "name": "m2",
                "type": "DIODE_NMOS",
                "connections": {
                    "drain": "inner",
                    "gate": "inSource",
                    "source": "source",
                },
            },
        ],
    },
]

subcircuits_cb = subcircuits_pmos_cb + subcircuits_nmos_cb
