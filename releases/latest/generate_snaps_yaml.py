import yaml
import argparse

def convert_to_yaml(output_table, canonical_livepatch):
    print(f"output_table = {output_table}")
    print(f"livepatch = {canonical_livepatch}")
    table_lines = output_table.splitlines()
    livepatch_line = canonical_livepatch.strip()

    # Extract livepatch info
    livepatch_channel, livepatch_revision = livepatch_line.split(":")
    livepatch_revision = livepatch_revision.strip(" ()")

    # Prepare the data for YAML
    packages = []

    # Process table file lines
    for line in table_lines:
        parts = line.split()
        print(parts)
        if len(parts) >= 3:
            package = {
                "name": parts[0],
                "revision": parts[1],
                "push_channel": parts[2]
            }
        else:
            print("len not >= 3")
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
    parser.add_argument('output_table', type=str, help='output_table')
    parser.add_argument('canonical_livepatch', type=str, help='canonical_livepatch')
    args = parser.parse_args()

    convert_to_yaml(args.output_table, args.canonical_livepatch)
