import os
import sys
import base64
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_skin_image(image_path):
    extension = image_path.split(".")[-1].lower()
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp"
    }
    media_type = media_types.get(extension, "image/jpeg")

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    print("Analyzing image... please wait.\n")

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": """You are a medical image analysis assistant 
                        specializing in dermatology and parasitology.
                        Analyze the uploaded skin image and provide:

                        1. DESCRIPTION: What you visually observe on the skin
                        2. POSSIBLE CONDITIONS: Potential skin or parasitic 
                           infections matching the symptoms, with likelihood 
                           (high / medium / low)
                        3. RISK FACTORS: Severity indicators and warning signs
                        4. RECOMMENDED ACTION: Whether the person should seek 
                           urgent care, routine care, or monitor at home

                        End every response with:
                        ⚠️ This is NOT a medical diagnosis. Please consult a 
                        licensed dermatologist or healthcare professional."""
                    }
                ]
            }
        ],
        max_tokens=1024
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py your_image.jpg")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"Error: File '{image_path}' not found.")
        sys.exit(1)

    result = analyze_skin_image(image_path)
    print("=" * 60)
    print("SKIN ANALYSIS RESULTS")
    print("=" * 60)
    print(result)
    print("=" * 60)
