def make_the_shitty_file_200(wire_list, utility_value):
    """Vytvoří formát pro tiskárnu (200 řádků, repeat 2)."""
    TARGET_DATA_LINES = 200
    header = "Pitch\tLine 1\tLine 2\tRepeat\tPitch Length\tCharacter Size\tOrientation\tUtility"
    footer = "3\t0\t0\t1\t0\t6\t0\t0\t1\t0\t9\t3\t5\t0\t0\t0\t0"
    output_lines = [header]
    
    for i, (_, row) in enumerate(wire_list.iterrows(), start=1):
        label = f"{row['Konec A']}/{row['Konec B']}"
        # Repeat 2 napevno pro oba konce
        line_content = f"{i}\t{label}\t\t2\t0\t4\t1\t{utility_value}"
        output_lines.append(line_content)
        
    for i in range(len(wire_list), TARGET_DATA_LINES):
        output_lines.append(f"{i + 1}\t\t\t\t\t\t\t")
    output_lines.append(footer)
    return "\n".join(output_lines)