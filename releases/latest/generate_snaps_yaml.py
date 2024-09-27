import yaml
import argparse

def convert_to_yaml(output_table_file, canonical_livepatch_file):
    # Read the output_table.txt
    with open(output_table_file, "r") as table_file:
        table_lines = table_file.readlines()

    # Read the canonical_livepatch.txt
    with open(canonical_livepatch_file, "r") as livepatch_file:
        livepatch_line = livepatch_file.read().strip()

    # Extract livepatch info
    livepatch_channel, livepatch_revision = livepatch_line.split(":")
    livepatch_revision = livepatch_revision.strip(" ()")

    # Prepare the data for YAML
    packages = []

    # Process table file lines
    for line in table_lines:
        parts = line.split()
        package = {
            "name": parts[0],
            "revision": parts[1],
            "push_channel": parts[2]
        }
        packages.append(package)

    # Add canonical-livepatch info
    packages.append({
        "name": "canonical-livepatch",
        "revision": livepatch_revision,
        "push_channel": livepatch_channel
    })

    # Write to YAML file
    with open("package-output.yaml", "w") as yaml_file:
        yaml.dump({"packages": packages}, yaml_file, default_flow_style=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert files to YAML.')
    parser.add_argument('output_table', type=str, help='Path to output_table.txt')
    parser.add_argument('canonical_livepatch', type=str, help='Path to canonical_livepatch.txt')
    args = parser.parse_args()

    convert_to_yaml(args.output_table, args.canonical_livepatch)
