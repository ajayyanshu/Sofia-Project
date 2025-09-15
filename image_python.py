import google.generativeai as genai
import os
from PIL import Image
from io import BytesIO
import base64

# --- Configuration ---
# It's best practice to load your API key from environment variables
# In Render, you would set GEMINI_API_KEY in your environment settings.
try:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("Error: GEMINI_API_KEY environment variable not set.")
    # Add a fallback or exit if the key isn't found
    exit()


def create_image_from_prompt(prompt, output_filename="generated_image.png"):
    """
    Generates an image from a text prompt using the Gemini API
    and saves it to a file.

    Args:
        prompt (str): The text description for the image to create.
        output_filename (str): The filename to save the generated image as.

    Returns:
        str: The path to the saved image file, or None if generation failed.
    """
    print(f"Generating image with prompt: '{prompt}'...")

    try:
        # Use the correct model for image generation
        model = genai.GenerativeModel('gemini-2.5-flash-image-preview')

        # The payload for text-to-image generation is simpler.
        # We just send the prompt and specify that we want an image back.
        response = model.generate_content(
            contents=prompt,
            generation_config={
                "response_mime_type": "image/png",
            }
        )

        # The image data comes back as base64-encoded bytes in the first part
        if response.candidates and response.candidates[0].content.parts:
            image_part = response.candidates[0].content.parts[0]
            
            # Check if the part contains inline image data
            if image_part.inline_data:
                image_bytes = image_part.inline_data.data
                
                # Decode the base64 string to bytes
                image_data = base64.b64decode(image_bytes)
                
                # Create an image object from the bytes
                image = Image.open(BytesIO(image_data))
                
                # Save the image to the specified file
                image.save(output_filename)
                print(f"Image successfully saved as {output_filename}")
                return output_filename
            else:
                print("Error: API response did not contain image data.")
                return None
        else:
            # This will print any blocking reason if the prompt was rejected
            print("Error: Image generation failed. Response:", response)
            return None

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# --- Example Usage ---
if __name__ == "__main__":
    # The prompt from your screenshot
    user_prompt = "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"
    
    # Call the function to generate and save the image
    create_image_from_prompt(user_prompt)
