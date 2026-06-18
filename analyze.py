import os
import sys

from dotenv import load_dotenv

from dermatica.vision import analyze_image_cli

load_dotenv()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py your_image.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' not found.")
        sys.exit(1)

    print("Analyzing image... please wait.\n")

    result = analyze_image_cli(image_path)
    print("=" * 60)
    print("SKIN ANALYSIS RESULTS")
    print("=" * 60)
    print(result)
    print("=" * 60)
