class HierarchicalLevel1:
    # https://www.electronics-tutorial.net/Analog-CMOS-Design/MOSFET-Amplifiers/CS-Amplifier-with-Active-Load/Fig1-CS-Amplifier-with-Active-Load.png
    subcircuits = [
        # Diode Transistor P
        {
            "name": "DIODE_PMOS",
            "type": "PMOS",
            "connections": {"S": "source", "G": "drain", "D": "drain"},
            "ports": ["drain", "gate", "source"],
        },
        # Diode Transistor N
        {
            "name": "DIODE_NMOS",
            "type": "NMOS",
            "connections": {"S": "source", "G": "drain", "D": "drain"},
            "ports": ["drain", "gate", "source"],
        },
    ]
