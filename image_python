import os
import io
from PIL import Image
import google.generativeai as genai

def setup_api_key():
    """Securely configures the API key from environment variables."""
    try:
        api_key = os.environ["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return True
    except KeyError:
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        return False

def generate_image_from_prompt(prompt_text):
    """
    Generates an image from a text prompt using the official Gemini API method.

    Args:
        prompt_text (str): The text description for the image.

    Returns:
        bytes: The raw image data in bytes if successful, otherwise None.
    """
    print(f"Attempting to generate image for prompt: '{prompt_text}'")
    
    # Initialize the Gemini Model for image generation
    model = genai.GenerativeModel('gemini-2.5-flash-image-preview')

    # Generate the content based on the prompt
    response = model.generate_content(prompt_text)

    # The response contains the image data directly in the first part
    try:
        # Extract the first candidate's content part which holds the image
        image_part = response.candidates[0].content.parts[0]

        # Check if the part contains the expected inline_data
        if image_part.inline_data:
            return image_part.inline_data.data
        else:
            # Handle cases where the model returns text (e.g., safety rejection)
            print("API did not return image data. Response:", image_part.text)
            return None
            
    except (IndexError, AttributeError) as e:
        print(f"Error processing API response: {e}")
        print("Full response:", response)
        return None

# --- Example of how to use this code ---
if __name__ == "__main__":
    # First, ensure the API key is set up
    if setup_api_key():
        # The prompt from your example
        user_prompt = "Create a picture of a nano banana dish in a fancy restaurant with a Gemini theme"
        
        # Call the function to get the image data
        image_data = generate_image_from_prompt(user_prompt)

        if image_data:
            # If we got data, open it with Pillow and save it
            try:
                image = Image.open(io.BytesIO(image_data))
                output_filename = "generated_image.png"
                image.save(output_filename)
                print(f"Image successfully generated and saved as '{output_filename}'")
            except Exception as e:
                print(f"Failed to save the image: {e}")
