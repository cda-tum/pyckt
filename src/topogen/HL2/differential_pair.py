subcircuits_diffpair = [
    {
        "name": "diffpair[p, 1]",
        "ports": ["input1", "input2", "output1", "output2", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "PMOS",
                "connections": {
                    "drain": "output1",
                    "gate": "input1",
                    "source": "source",
                },
            },
            {
                "name": "m2",
                "type": "PMOS",
                "connections": {
                    "drain": "output2",
                    "gate": "input2",
                    "source": "source",
                },
            },
        ],
    },
    {
        "name": "diffpair[n, 1]",
        "ports": ["input1", "input2", "output1", "output2", "source"],
        "instances": [
            {
                "name": "m1",
                "type": "NMOS",
                "connections": {
                    "drain": "output1",
                    "gate": "input1",
                    "source": "source",
                },
            },
            {
                "name": "m2",
                "type": "NMOS",
                "connections": {
                    "drain": "output2",
                    "gate": "input2",
                    "source": "source",
                },
            },
        ],
    },
]
