"""
============================================================================
GEOMETRY UTILS - Utilitaires Calculs Géométriques
============================================================================
Fonctions pour calculs géométriques 3D (distances, volumes, dimensions, etc.)
"""

import numpy as np
from typing import Tuple, List, Optional
import math


class GeometryUtils:
    """Utilitaires pour calculs géométriques"""

    @staticmethod
    def calculate_distance_3d(point1: Tuple[float, float, float],
                             point2: Tuple[float, float, float]) -> float:
        """
        Calcule distance euclidienne entre 2 points 3D

        Args:
            point1: (x, y, z) premier point
            point2: (x, y, z) second point

        Returns:
            Distance en mètres
        """
        return math.sqrt(
            (point2[0] - point1[0])**2 +
            (point2[1] - point1[1])**2 +
            (point2[2] - point1[2])**2
        )

    @staticmethod
    def calculate_bounding_box_volume(bbox_min: Tuple[float, float, float],
                                     bbox_max: Tuple[float, float, float]) -> float:
        """
        Calcule volume d'une bounding box

        Args:
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            Volume en m³
        """
        width = bbox_max[0] - bbox_min[0]
        depth = bbox_max[1] - bbox_min[1]
        height = bbox_max[2] - bbox_min[2]

        return abs(width * depth * height)

    @staticmethod
    def get_max_dimension(bbox_min: Tuple[float, float, float],
                         bbox_max: Tuple[float, float, float]) -> float:
        """
        Obtient la dimension maximale d'un objet

        Args:
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            Dimension max en mètres
        """
        width = abs(bbox_max[0] - bbox_min[0])
        depth = abs(bbox_max[1] - bbox_min[1])
        height = abs(bbox_max[2] - bbox_min[2])

        return max(width, depth, height)

    @staticmethod
    def get_diagonal_dimension(bbox_min: Tuple[float, float, float],
                              bbox_max: Tuple[float, float, float]) -> float:
        """
        Calcule dimension diagonale d'un objet (pour passage par porte)

        Args:
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            Diagonale en mètres
        """
        width = bbox_max[0] - bbox_min[0]
        depth = bbox_max[1] - bbox_min[1]

        # Diagonale 2D (ignorant hauteur)
        return math.sqrt(width**2 + depth**2)

    @staticmethod
    def get_centroid(bbox_min: Tuple[float, float, float],
                    bbox_max: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        Calcule centre géométrique (centroïde)

        Args:
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            (x, y, z) du centre
        """
        return (
            (bbox_min[0] + bbox_max[0]) / 2,
            (bbox_min[1] + bbox_max[1]) / 2,
            (bbox_min[2] + bbox_max[2]) / 2
        )

    @staticmethod
    def is_point_in_bbox(point: Tuple[float, float, float],
                        bbox_min: Tuple[float, float, float],
                        bbox_max: Tuple[float, float, float]) -> bool:
        """
        Vérifie si un point est dans une bounding box

        Args:
            point: (x, y, z) point à tester
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            True si point dans bbox
        """
        return (
            bbox_min[0] <= point[0] <= bbox_max[0] and
            bbox_min[1] <= point[1] <= bbox_max[1] and
            bbox_min[2] <= point[2] <= bbox_max[2]
        )

    @staticmethod
    def calculate_floor_area(bbox_min: Tuple[float, float, float],
                           bbox_max: Tuple[float, float, float]) -> float:
        """
        Calcule surface au sol

        Args:
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            Surface en m²
        """
        width = abs(bbox_max[0] - bbox_min[0])
        depth = abs(bbox_max[1] - bbox_min[1])

        return width * depth

    @staticmethod
    def get_height(bbox_min: Tuple[float, float, float],
                  bbox_max: Tuple[float, float, float]) -> float:
        """
        Obtient hauteur d'un objet

        Args:
            bbox_min: (x_min, y_min, z_min)
            bbox_max: (x_max, y_max, z_max)

        Returns:
            Hauteur en mètres
        """
        return abs(bbox_max[2] - bbox_min[2])

    @staticmethod
    def meters_to_cm(value_m: float) -> float:
        """Convertit mètres en centimètres"""
        return value_m * 100

    @staticmethod
    def cm_to_meters(value_cm: float) -> float:
        """Convertit centimètres en mètres"""
        return value_cm / 100

    @staticmethod
    def cubic_meters_to_liters(value_m3: float) -> float:
        """Convertit m³ en litres"""
        return value_m3 * 1000

    @staticmethod
    def calculate_minimum_door_width(equipment_max_dim_m: float,
                                     margin_cm: float = 20) -> float:
        """
        Calcule largeur porte minimale pour passage équipement

        Args:
            equipment_max_dim_m: Dimension max équipement en mètres
            margin_cm: Marge de sécurité en cm

        Returns:
            Largeur porte minimale en mètres
        """
        return equipment_max_dim_m + (margin_cm / 100)

    @staticmethod
    def format_coordinates(coords: Tuple[float, float, float],
                          precision: int = 2) -> str:
        """
        Formate coordonnées pour affichage

        Args:
            coords: (x, y, z)
            precision: Nombre décimales

        Returns:
            String formaté "X: 12.34, Y: 56.78, Z: 90.12"
        """
        return f"X: {coords[0]:.{precision}f}, Y: {coords[1]:.{precision}f}, Z: {coords[2]:.{precision}f}"

    @staticmethod
    def parse_ifc_point(ifc_point) -> Tuple[float, float, float]:
        """
        Parse un point IFC en tuple Python

        Args:
            ifc_point: Point IFC (IfcCartesianPoint)

        Returns:
            (x, y, z)
        """
        coords = ifc_point.Coordinates

        # Assurer 3 coordonnées
        if len(coords) == 2:
            return (coords[0], coords[1], 0.0)
        elif len(coords) == 3:
            return (coords[0], coords[1], coords[2])
        else:
            return (0.0, 0.0, 0.0)


# === FONCTIONS UTILITAIRES RAPIDES ===

def distance(p1: Tuple, p2: Tuple) -> float:
    """Alias rapide pour distance 3D"""
    return GeometryUtils.calculate_distance_3d(p1, p2)

def volume(bbox_min: Tuple, bbox_max: Tuple) -> float:
    """Alias rapide pour volume"""
    return GeometryUtils.calculate_bounding_box_volume(bbox_min, bbox_max)

def centroid(bbox_min: Tuple, bbox_max: Tuple) -> Tuple:
    """Alias rapide pour centroïde"""
    return GeometryUtils.get_centroid(bbox_min, bbox_max)
