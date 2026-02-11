"""
Gemini Image Generation - MemAgent

Tool for generating photorealistic images using Google's Gemini 2.5 Flash Image (Nano Banana) model.
Supports reference images for likeness of people and pets (text-and-image-to-image).
CRITICAL: Returns file paths only, not image bytes, to prevent token waste.
"""

import os
from datetime import datetime
from typing import List, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.core.monitoring import logger


class GeminiImageGenerator:
    """
    Generates photorealistic images using Gemini 2.5 Flash Image.
    
    CRITICAL TOKEN OPTIMIZATION:
    - Accepts reference image URLs (not bytes)
    - Returns generated image as file path
    - Never loads image bytes into memory for LLM context
    """
    
    # Model name for Gemini image generation
    MODEL_NAME = "gemini-2.5-flash-image"  # Nano Banana image generation model
    
    # Token cost per image generation
    TOKENS_PER_IMAGE = 1290
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Gemini image generator.
        
        Args:
            api_key: Google API key (uses settings if None)
        """
        self.api_key = api_key or settings.google_api_key
        self.client = genai.Client(api_key=self.api_key)
    
    async def generate_image(
        self,
        prompt: str,
        user_id: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        reference_image_bytes: Optional[List[bytes]] = None,
        output_dir: Optional[str] = None,
        aspect_ratio: str = "1:1"
    ) -> Optional[str]:
        """
        Generate a photorealistic image from a text prompt, optionally using reference images for likeness.
        
        Args:
            prompt: Text description of the image to generate
            user_id: User ID for secure file naming (included in filename)
            reference_image_urls: Optional list of reference image URLs (unused if reference_image_bytes provided)
            reference_image_bytes: Optional list of image bytes (e.g. from Picker) for people/pet likeness
            output_dir: Directory to save generated image (uses temp dir if None)
            aspect_ratio: Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
            
        Returns:
            Path to generated image file, or None if generation failed
        """
        try:
            if output_dir is None:
                output_dir = settings.temp_image_dir
            
            os.makedirs(output_dir, exist_ok=True)
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            if user_id:
                output_path = os.path.join(output_dir, f"memory_{user_id}_{timestamp}.jpg")
            else:
                output_path = os.path.join(output_dir, f"memory_{timestamp}.jpg")
            
            ref_count = len(reference_image_bytes) if reference_image_bytes else 0
            logger.info(
                "image_generation_requested",
                prompt_length=len(prompt),
                has_references=ref_count > 0,
                reference_count=ref_count,
                aspect_ratio=aspect_ratio,
                user_id=user_id
            )
            
            # Build contents: prompt + optional reference images for likeness
            if reference_image_bytes:
                likeness_instruction = (
                    " Use the attached reference photos to match the likeness of the people and pets "
                    "in the scene. Keep their appearance consistent with these references."
                )
                full_prompt = prompt.rstrip() + likeness_instruction
                parts = [types.Part(text=full_prompt)]
                for img_bytes in reference_image_bytes[:8]:
                    mime = "image/png" if img_bytes[:8].startswith(b"\x89PNG") else "image/jpeg"
                    parts.append(
                        types.Part(inline_data=types.Blob(data=img_bytes, mime_type=mime))
                    )
                contents = parts
                config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            else:
                contents = [prompt]
                config = None
            
            try:
                if config is not None:
                    response = self.client.models.generate_content(
                        model=self.MODEL_NAME,
                        contents=contents,
                        config=config
                    )
                else:
                    response = self.client.models.generate_content(
                        model=self.MODEL_NAME,
                        contents=contents
                    )
                
                for part in response.parts:
                    if part.inline_data is not None:
                        with open(output_path, 'wb') as f:
                            f.write(part.inline_data.data)
                        logger.info(
                            "image_generated_successfully",
                            output_path=output_path,
                            file_size=len(part.inline_data.data),
                            user_id=user_id
                        )
                        return output_path
                
                logger.warning("image_generation_no_data", message="No image data in response", user_id=user_id)
                return None
                
            except Exception as sdk_error:
                logger.error("image_generation_sdk_error", error=str(sdk_error), user_id=user_id)
                return None
            
        except Exception as e:
            logger.error(
                "image_generation_failed",
                error=str(e),
                prompt_preview=prompt[:100]
            )
            return None
    
    async def edit_image(
        self,
        image_path: str,
        edit_instruction: str,
        user_id: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        Edit an existing image with a text instruction (image-to-image).
        Returns path to the new image file.
        """
        if output_dir is None:
            output_dir = settings.temp_image_dir
        try:
            if not os.path.isfile(image_path):
                logger.warning("edit_image_file_missing", image_path=image_path)
                return None
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            mime = "image/png" if image_bytes[:8].startswith(b"\x89PNG") else "image/jpeg"
            prompt = (
                f"Apply these changes to the image. Keep the rest of the scene and people the same. "
                f"User requested: {edit_instruction}"
            )
            parts = [
                types.Part(inline_data=types.Blob(data=image_bytes, mime_type=mime)),
                types.Part(text=prompt),
            ]
            config = types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"])
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            out_name = f"memory_{user_id}_{timestamp}.jpg" if user_id else f"memory_{timestamp}.jpg"
            output_path = os.path.join(output_dir, out_name)
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=parts,
                config=config
            )
            for part in response.parts:
                if part.inline_data is not None:
                    with open(output_path, "wb") as f:
                        f.write(part.inline_data.data)
                    logger.info("image_edit_success", output_path=output_path, user_id=user_id)
                    return output_path
            logger.warning("edit_image_no_data", user_id=user_id)
            return None
        except Exception as e:
            logger.error("image_edit_failed", error=str(e), image_path=image_path)
            return None
    
    def craft_prompt(
        self,
        what_happened: str,
        location: Optional[str] = None,
        time_of_day: Optional[str] = None,
        people_descriptions: Optional[List[str]] = None,
        mood: Optional[str] = None,
        style: str = "photorealistic"
    ) -> str:
        """
        Craft a detailed prompt for image generation.
        
        Args:
            what_happened: Main event/scene description
            location: Location description
            time_of_day: Time of day (morning, afternoon, evening, night, sunset)
            people_descriptions: Descriptions of people in the scene
            mood: Emotional mood/atmosphere
            style: Art style (default: "photorealistic")
            
        Returns:
            Crafted prompt string
        """
        prompt_parts = []
        
        # Style directive
        prompt_parts.append(f"A {style}, high-quality photograph")
        
        # Main scene
        prompt_parts.append(f"of {what_happened}")
        
        # People
        if people_descriptions:
            people_desc = ", ".join(people_descriptions)
            prompt_parts.append(f"with {people_desc}")
        
        # Location
        if location:
            prompt_parts.append(f"at {location}")
        
        # Time of day
        if time_of_day:
            prompt_parts.append(f"during {time_of_day}")
        
        # Mood/atmosphere
        if mood:
            prompt_parts.append(f"with a {mood} atmosphere")
        
        # Quality and style tags
        prompt_parts.append("captured with natural lighting, authentic details, 35mm film aesthetic")
        
        prompt = " ".join(prompt_parts) + "."
        
        logger.info(
            "prompt_crafted",
            prompt_length=len(prompt),
            has_people=people_descriptions is not None,
            has_location=location is not None
        )
        
        return prompt
    
    def estimate_tokens(self, prompt: str, has_references: bool = False) -> int:
        """
        Estimate token usage for image generation.
        
        Args:
            prompt: Text prompt
            has_references: Whether reference images are included
            
        Returns:
            Estimated token count
        """
        # Base cost for image generation
        tokens = self.TOKENS_PER_IMAGE
        
        # Add tokens for prompt (rough estimate: 1 token per 4 chars)
        tokens += len(prompt) // 4
        
        # Reference images add to context (if we were using them in prompt)
        if has_references:
            tokens += 500  # Approximate overhead
        
        return tokens
