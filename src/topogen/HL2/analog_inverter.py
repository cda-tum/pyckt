subcircuits_inv = [
    {
        "name": "AnalogInverter[?, 1]",
        "ports": [
            "inCurrentBiasNmos",
            "inCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 1]",
                "connections": {
                    "in": "inCurrentBiasNmos",
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 1]",
                "connections": {
                    "in": "inCurrentBiasPmos",
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 2]",
        "ports": [
            "inCurrentBiasPmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 2]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                    "inOutput": "inOutputCurrentBiasNmos",
                    "inSource": "inSourceCurrentBiasNmos",
                    "inner": "innerCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 1]",
                "connections": {
                    "in": "inCurrentBiasPmos",
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 3]",
        "ports": [
            "inCurrentBiasPmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 3]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                    "inOutput": "inOutputCurrentBiasNmos",
                    "inSource": "inSourceCurrentBiasNmos",
                    "inner": "innerCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 1]",
                "connections": {
                    "in": "inCurrentBiasPmos",
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 4]",
        "ports": [
            "inCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 1]",
                "connections": {
                    "in": "inCurrentBiasNmos",
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 2]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                    "inOutput": "inOutputCurrentBiasPmos",
                    "inSource": "inSourceCurrentBiasPmos",
                    "inner": "innerCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 5]",
        "ports": [
            "inOutputCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasNmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasNmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 2]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                    "inOutput": "inOutputCurrentBiasNmos",
                    "inSource": "inSourceCurrentBiasNmos",
                    "inner": "innerCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 2]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                    "inOutput": "inOutputCurrentBiasPmos",
                    "inSource": "inSourceCurrentBiasPmos",
                    "inner": "innerCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 6]",
        "ports": [
            "inOutputCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasNmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasNmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 3]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                    "inOutput": "inOutputCurrentBiasNmos",
                    "inSource": "inSourceCurrentBiasNmos",
                    "inner": "innerCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 3]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                    "inOutput": "inOutputCurrentBiasPmos",
                    "inSource": "inSourceCurrentBiasPmos",
                    "inner": "innerCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 7]",
        "ports": [
            "inCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 1]",
                "connections": {
                    "in": "inCurrentBiasNmos",
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 2]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                    "inOutput": "inOutputCurrentBiasPmos",
                    "inSource": "inSourceCurrentBiasPmos",
                    "inner": "innerCurrentBiasPmos",
                },
            },
        ],
    },
    {
        "name": "AnalogInverter[?, 8]",
        "ports": [
            "inOutputCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasNmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasNmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        ],
        "instances": [
            {
                "name": "m1",
                "type": "CurrentBias[n, 3]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasNmos",
                    "inOutput": "inOutputCurrentBiasNmos",
                    "inSource": "inSourceCurrentBiasNmos",
                    "inner": "innerCurrentBiasNmos",
                },
            },
            {
                "name": "m2",
                "type": "CurrentBias[p, 3]",
                "connections": {
                    "out": "output",
                    "source": "sourceCurrentBiasPmos",
                    "inOutput": "inOutputCurrentBiasPmos",
                    "inSource": "inSourceCurrentBiasPmos",
                    "inner": "innerCurrentBiasPmos",
                },
            },
        ],
    },
]
