"""
EXIF Metadata Writer - MemAgent

Embeds comprehensive EXIF/GPS/IPTC metadata into generated images.
"""

import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import piexif
from PIL import Image

from app.core.monitoring import logger


class EXIFWriter:
    """
    Writes EXIF metadata to images including DateTime, GPS, IPTC keywords, and custom fields.
    """
    
    @staticmethod
    def decimal_to_dms(decimal: float) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
        """
        Convert decimal degrees to degrees/minutes/seconds.
        
        Args:
            decimal: Decimal degrees
            
        Returns:
            Tuple of (degrees, minutes, seconds) as rational numbers
        """
        is_positive = decimal >= 0
        decimal = abs(decimal)
        
        degrees = int(decimal)
        minutes_float = (decimal - degrees) * 60
        minutes = int(minutes_float)
        seconds = (minutes_float - minutes) * 60
        seconds_int = int(seconds * 100)
        
        return (
            (degrees, 1),
            (minutes, 1),
            (seconds_int, 100)
        )
    
    @staticmethod
    def embed_exif_metadata(
        image_path: str,
        output_path: Optional[str] = None,
        memory_date: Optional[datetime] = None,
        gps_coordinates: Optional[Dict[str, float]] = None,
        location_name: Optional[str] = None,
        description: Optional[str] = None,
        people_tags: Optional[List[str]] = None,
        pet_tags: Optional[List[str]] = None,
        custom_fields: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Embed comprehensive EXIF metadata into an image.
        
        Args:
            image_path: Path to source image
            output_path: Path for output image (if None, overwrites source)
            memory_date: Date/time of the memory
            gps_coordinates: Dict with 'latitude' and 'longitude' keys
            location_name: Human-readable location name
            description: Full memory story (max 2000 chars)
            people_tags: List of people names
            pet_tags: List of pet names
            custom_fields: Custom XMP fields
            
        Returns:
            Path to the output image
            
        Raises:
            ValueError: If image cannot be processed
        """
        if output_path is None:
            output_path = image_path
        
        try:
            # Load image
            img = Image.open(image_path)
            
            # Initialize EXIF dict
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
            
            # Try to load existing EXIF if present
            try:
                if "exif" in img.info:
                    exif_dict = piexif.load(img.info["exif"])
            except Exception:
                pass  # Use empty dict if loading fails
            
            # DateTime - Memory date
            if memory_date:
                datetime_str = memory_date.strftime("%Y:%m:%d %H:%M:%S")
                exif_dict["0th"][piexif.ImageIFD.DateTime] = datetime_str.encode()
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = datetime_str.encode()
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = datetime_str.encode()
            
            # GPS Coordinates
            if gps_coordinates and "latitude" in gps_coordinates and "longitude" in gps_coordinates:
                lat = gps_coordinates["latitude"]
                lng = gps_coordinates["longitude"]
                
                # Latitude
                lat_dms = EXIFWriter.decimal_to_dms(abs(lat))
                exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = lat_dms
                exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = b"N" if lat >= 0 else b"S"
                
                # Longitude
                lng_dms = EXIFWriter.decimal_to_dms(abs(lng))
                exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = lng_dms
                exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b"E" if lng >= 0 else b"W"
            
            # Image Description - Full story
            if description:
                desc_truncated = description[:2000]  # EXIF has size limits
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = desc_truncated.encode("utf-8")
            
            # User Comment - Additional context
            if location_name or people_tags or pet_tags:
                comment_parts = []
                if location_name:
                    comment_parts.append(f"Location: {location_name}")
                if people_tags:
                    comment_parts.append(f"People: {', '.join(people_tags)}")
                if pet_tags:
                    comment_parts.append(f"Pets: {', '.join(pet_tags)}")
                
                comment = "; ".join(comment_parts)
                # User comment needs special encoding for EXIF
                user_comment = b"ASCII\x00\x00\x00" + comment.encode("utf-8")
                exif_dict["Exif"][piexif.ExifIFD.UserComment] = user_comment
            
            # Software tag - Mark as generated by MemAgent
            exif_dict["0th"][piexif.ImageIFD.Software] = b"MemAgent AI Memory Generator"
            
            # Artist tag - Could include people names
            if people_tags:
                artist = ", ".join(people_tags)
                exif_dict["0th"][piexif.ImageIFD.Artist] = artist.encode("utf-8")[:100]  # Limit length
            
            # Dump EXIF to bytes
            exif_bytes = piexif.dump(exif_dict)
            
            # Save image with EXIF
            img.save(output_path, exif=exif_bytes, quality=95)
            
            logger.info(
                "exif_embedded",
                image_path=image_path,
                output_path=output_path,
                has_gps=gps_coordinates is not None,
                has_datetime=memory_date is not None,
                people_count=len(people_tags) if people_tags else 0,
                pet_count=len(pet_tags) if pet_tags else 0
            )
            
            return output_path
            
        except Exception as e:
            logger.error(
                "exif_embedding_failed",
                image_path=image_path,
                error=str(e)
            )
            raise ValueError(f"Failed to embed EXIF metadata: {str(e)}")
    
    @staticmethod
    def read_exif_metadata(image_path: str) -> Dict:
        """
        Read EXIF metadata from an image.
        
        Args:
            image_path: Path to image
            
        Returns:
            Dict with EXIF data
        """
        try:
            img = Image.open(image_path)
            if "exif" not in img.info:
                return {}
            
            exif_dict = piexif.load(img.info["exif"])
            
            # Extract key fields
            metadata = {}
            
            # DateTime
            if piexif.ImageIFD.DateTime in exif_dict["0th"]:
                metadata["datetime"] = exif_dict["0th"][piexif.ImageIFD.DateTime].decode()
            
            # Description
            if piexif.ImageIFD.ImageDescription in exif_dict["0th"]:
                metadata["description"] = exif_dict["0th"][piexif.ImageIFD.ImageDescription].decode("utf-8")
            
            # GPS
            if piexif.GPSIFD.GPSLatitude in exif_dict["GPS"]:
                metadata["has_gps"] = True
            
            return metadata
            
        except Exception as e:
            logger.error("exif_read_failed", image_path=image_path, error=str(e))
            return {}
