# image_python.py
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

# Initialize Gemini client
client = genai.Client()

# Text prompt for image generation
prompt = (
    "Create a picture of my cat eating a nano-banana in a "
    "fancy restaurant under the Gemini constellation"
)

# Optional: input image path
input_image_path = "/path/to/cat_image.png"

# Open image if you want to use it as reference
try:
    image = Image.open(input_image_path)
    contents = [prompt, image]
except FileNotFoundError:
    print(f"Image not found at {input_image_path}, generating from text only.")
    contents = [prompt]

# Generate image with Gemini API
response = client.models.generate_content(
    model="gemini-2.5-flash-image-preview",
    contents=contents,
)

# Save generated image(s)
for part in response.candidates[0].content.parts:
    if part.text is not None:
        print("Generated text:", part.text)
    elif part.inline_data is not None:
        generated_image = Image.open(BytesIO(part.inline_data.data))
        output_path = "generated_image.png"
        generated_image.save(output_path)
        print(f"Image saved at: {output_path}")
