"""
IFC EXTRACTOR - Extraction avec support 2 fichiers IFC :
Version modifiee pour accepter 2 fichiers IFC (Architecture + Electrique)
et fusionner les donnees automatiquement.

Gere :
- La conversion automatique des unites (cm -> m)
- L'alignement des coordonnees entre 2 fichiers IFC
"""

import ifcopenshell
import ifcopenshell.geom
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path

from shared.logger import logger
from shared.geometry_utils import GeometryUtils


class IFCExtractor:
    """Extracteur de donnees depuis fichiers IFC (support 2 fichiers)"""
    def __init__(self, ifc_path: str, ifc_path_elec: str = None):
        self.ifc_path = Path(ifc_path)
        self.ifc_path_elec = Path(ifc_path_elec) if ifc_path_elec else None
        self.ifc_file = None
        self.ifc_file_elec = None
        self.settings = None

        # Facteurs de conversion
        self.unit_scale_archi = 1.0
        self.unit_scale_elec = 1.0

        # Decalage pour aligner ELEC sur ARCHI
        self.offset_elec = (0.0, 0.0, 0.0)

        # Donnees extraites
        self.spaces = []
        self.equipment = []
        self.doors = []
        self.slabs = []

        if self.ifc_path_elec:
            logger.info(f"  Mode 2 fichiers:")
            logger.info(f"   - Architecture: {self.ifc_path.name}")
            logger.info(f"   - Electrique: {self.ifc_path_elec.name}")
        else:
            logger.info(f"  Fichier unique: {self.ifc_path.name}")

    def _detect_unit_scale(self, ifc_file) -> float:
        """Detecte le facteur de conversion vers metres"""
        try:
            units = ifc_file.by_type("IfcUnitAssignment")
            if units:
                for unit_assign in units:
                    for unit in unit_assign.Units:
                        if hasattr(unit, 'UnitType') and unit.UnitType == 'LENGTHUNIT':
                            prefix = getattr(unit, 'Prefix', None)
                            if prefix == 'CENTI':
                                return 0.01  # cm -> m
                            elif prefix == 'MILLI':
                                return 0.001  # mm -> m
                            else:
                                return 1.0  # deja en metres
        except:
            pass
        return 1.0

    def _get_site_origin(self, ifc_file) -> Tuple[float, float, float]:
        """Recupere l'origine du site IFC"""
        try:
            sites = ifc_file.by_type("IfcSite")
            for site in sites:
                if hasattr(site, 'ObjectPlacement') and site.ObjectPlacement:
                    placement = site.ObjectPlacement
                    if hasattr(placement, 'RelativePlacement') and placement.RelativePlacement:
                        rp = placement.RelativePlacement
                        if hasattr(rp, 'Location') and rp.Location:
                            coords = rp.Location.Coordinates
                            return (float(coords[0]), float(coords[1]), float(coords[2]))
        except:
            pass
        return (0.0, 0.0, 0.0)

    def _compute_alignment_offset(self):
        """
        Calcule le decalage pour aligner les coordonnees ELEC sur ARCHI.
        Utilise les bounding boxes globales pour estimer le decalage.
        """
        if not self.ifc_file_elec:
            return

        logger.info("   Calcul alignement ARCHI <-> ELEC...")

        # Calculer bbox globale ARCHI (a partir des spaces)
        # Note: ifcopenshell.geom retourne deja en metres
        archi_bbox = self._compute_global_bbox(self.ifc_file, "IfcSpace", max_elements=100)

        # Calculer bbox globale ELEC (a partir des produits electriques)
        elec_bbox = self._compute_global_bbox_equipment(self.ifc_file_elec, max_elements=100)

        if not archi_bbox or not elec_bbox:
            logger.warning("   Impossible de calculer l'alignement - pas assez de donnees")
            return

        # Decalage = centre ARCHI - centre ELEC
        archi_cx = (archi_bbox['min'][0] + archi_bbox['max'][0]) / 2
        archi_cy = (archi_bbox['min'][1] + archi_bbox['max'][1]) / 2
        archi_cz = (archi_bbox['min'][2] + archi_bbox['max'][2]) / 2

        elec_cx = (elec_bbox['min'][0] + elec_bbox['max'][0]) / 2
        elec_cy = (elec_bbox['min'][1] + elec_bbox['max'][1]) / 2
        elec_cz = (elec_bbox['min'][2] + elec_bbox['max'][2]) / 2

        self.offset_elec = (
            archi_cx - elec_cx,
            archi_cy - elec_cy,
            archi_cz - elec_cz
        )

        logger.info(f"   Centre ARCHI: ({archi_cx:.2f}, {archi_cy:.2f}, {archi_cz:.2f}) m")
        logger.info(f"   Centre ELEC:  ({elec_cx:.2f}, {elec_cy:.2f}, {elec_cz:.2f}) m")
        logger.info(f"   Decalage applique: dx={self.offset_elec[0]:.2f}, dy={self.offset_elec[1]:.2f}, dz={self.offset_elec[2]:.2f} m")

    def _compute_global_bbox(self, ifc_file, ifc_type, max_elements=100):
        """Calcule la bounding box globale pour un type d'element.
        Note: ifcopenshell.geom retourne deja les coords en metres."""
        elements = ifc_file.by_type(ifc_type)
        all_x, all_y, all_z = [], [], []
        for elem in elements[:max_elements]:
            try:
                shape = ifcopenshell.geom.create_shape(self.settings, elem)
                verts = shape.geometry.verts
                all_x.extend(verts[i] for i in range(0, len(verts), 3))
                all_y.extend(verts[i] for i in range(1, len(verts), 3))
                all_z.extend(verts[i] for i in range(2, len(verts), 3))
            except:
                pass
        if all_x:
            return {
                'min': (min(all_x), min(all_y), min(all_z)),
                'max': (max(all_x), max(all_y), max(all_z))
            }
        return None

    def _compute_global_bbox_equipment(self, ifc_file, max_elements=100):
        """Calcule la bounding box globale des equipements electriques.
        Note: ifcopenshell.geom retourne deja les coords en metres."""
        all_products = ifc_file.by_type("IfcProduct")
        keywords = ['elec', 'light', 'lampe', 'transfo', 'armoire',
                     'tableau', 'prise', 'inter', 'switch']
        all_x, all_y, all_z = [], [], []
        count = 0
        for product in all_products:
            if count >= max_elements:
                break
            name = str(product.Name or "").lower()
            if any(kw in name for kw in keywords):
                try:
                    shape = ifcopenshell.geom.create_shape(self.settings, product)
                    verts = shape.geometry.verts
                    all_x.extend(verts[i] for i in range(0, len(verts), 3))
                    all_y.extend(verts[i] for i in range(1, len(verts), 3))
                    all_z.extend(verts[i] for i in range(2, len(verts), 3))
                    count += 1
                except:
                    pass
        if all_x:
            return {
                'min': (min(all_x), min(all_y), min(all_z)),
                'max': (max(all_x), max(all_y), max(all_z))
            }
        return None

    def load_ifc_file(self) -> bool:
        """Charge le(s) fichier(s) IFC"""
        try:
            logger.info(f"   Chargement {self.ifc_path.name}...")
            self.ifc_file = ifcopenshell.open(str(self.ifc_path))

            self.settings = ifcopenshell.geom.settings()
            self.settings.set(self.settings.USE_WORLD_COORDS, True)

            total = len(list(self.ifc_file.by_type("IfcProduct")))
            logger.info(f"  Fichier principal: {total} elements")

            # Detecter unites ARCHI
            self.unit_scale_archi = self._detect_unit_scale(self.ifc_file)
            logger.info(f"   Unite ARCHI: facteur={self.unit_scale_archi} (1cm={self.unit_scale_archi}m)")

            # Charger fichier electrique si fourni
            if self.ifc_path_elec:
                logger.info(f"   Chargement {self.ifc_path_elec.name}...")
                self.ifc_file_elec = ifcopenshell.open(str(self.ifc_path_elec))

                total_elec = len(list(self.ifc_file_elec.by_type("IfcProduct")))
                logger.info(f"  Fichier electrique: {total_elec} elements")

                # Detecter unites ELEC
                self.unit_scale_elec = self._detect_unit_scale(self.ifc_file_elec)
                logger.info(f"   Unite ELEC: facteur={self.unit_scale_elec}")

                # Calculer alignement
                self._compute_alignment_offset()

            return True

        except Exception as e:
            logger.error(f"  Erreur chargement IFC: {str(e)}")
            return False

    def extract_all(self) -> Dict:
        """Lance extraction complete"""
        if not self.ifc_file:
            if not self.load_ifc_file():
                return {}

        logger.section_header("EXTRACTION DONNEES IFC")

        self.extract_spaces()
        self.extract_equipment()
        self.extract_doors()
        self.extract_slabs()

        summary = {
            "spaces": len(self.spaces),
            "equipment": len(self.equipment),
            "doors": len(self.doors),
            "slabs": len(self.slabs)
        }

        logger.info(f"\n   Extraction terminee:")
        logger.info(f"   - Spaces: {summary['spaces']}")
        logger.info(f"   - Equipment: {summary['equipment']}")
        logger.info(f"   - Doors: {summary['doors']}")
        logger.info(f"   - Slabs: {summary['slabs']}")

        return {
            "spaces": self.spaces,
            "equipment": self.equipment,
            "doors": self.doors,
            "slabs": self.slabs,
            "summary": summary
        }

    def extract_spaces(self):
        """Extrait espaces (depuis fichier principal/archi)"""
        logger.info(" Extraction Spaces...")
        spaces_ifc = self.ifc_file.by_type("IfcSpace")

        for space in spaces_ifc:
            try:
                space_data = self._parse_space(space, self.ifc_file)
                if space_data:
                    self.spaces.append(space_data)
            except Exception as e:
                logger.error(f"Erreur space {space.GlobalId}: {str(e)}")

        logger.info(f"  {len(self.spaces)} spaces extraits")

    def extract_equipment(self):
        """Extrait equipements (depuis fichier elec si disponible)"""
        logger.info(" Extraction Equipment...")

        source_file = self.ifc_file_elec if self.ifc_file_elec else self.ifc_file

        if self.ifc_file_elec:
            logger.info("   -> Source: Fichier ELECTRIQUE")

        try:
            all_products = source_file.by_type("IfcProduct")

            for product in all_products:
                name = str(product.Name or "").lower()

                keywords = ['elec', 'light', 'lampe', 'transfo', 'armoire',
                             'tableau', 'prise', 'inter', 'switch']

                if any(kw in name for kw in keywords):
                    try:
                        eq_data = self._parse_equipment(product, source_file)
                        if eq_data:
                            self.equipment.append(eq_data)
                    except:
                        pass

        except Exception as e:
            logger.error(f"Erreur equipment: {str(e)}")

        logger.info(f"  {len(self.equipment)} equipements extraits")

    def extract_doors(self):
        """Extrait portes (depuis fichier principal/archi)"""
        logger.info(" Extraction Doors...")
        doors_ifc = self.ifc_file.by_type("IfcDoor")

        for door in doors_ifc:
            try:
                door_data = self._parse_door(door, self.ifc_file)
                if door_data:
                    self.doors.append(door_data)
            except Exception as e:
                logger.error(f"Erreur door {door.GlobalId}: {str(e)}")

        logger.info(f"  {len(self.doors)} portes extraites")

    def extract_slabs(self):
        """Extrait dalles (depuis fichier principal/archi)"""
        logger.info(" Extraction Slabs...")
        slabs_ifc = self.ifc_file.by_type("IfcSlab")

        for slab in slabs_ifc:
            try:
                slab_data = self._parse_slab(slab, self.ifc_file)
                if slab_data:
                    self.slabs.append(slab_data)
            except Exception as e:
                logger.error(f"Erreur slab {slab.GlobalId}: {str(e)}")

        logger.info(f"  {len(self.slabs)} dalles extraites")

    # === METHODES DE PARSING ===

    def _get_bounding_box(self, element, source_file) -> Optional[Dict]:
        """Calcule bounding box (ifcopenshell.geom retourne deja en metres)"""
        try:
            shape = ifcopenshell.geom.create_shape(self.settings, element)
            verts = shape.geometry.verts

            x_coords = [verts[i] for i in range(0, len(verts), 3)]
            y_coords = [verts[i] for i in range(1, len(verts), 3)]
            z_coords = [verts[i] for i in range(2, len(verts), 3)]

            return {
                'min': (min(x_coords), min(y_coords), min(z_coords)),
                'max': (max(x_coords), max(y_coords), max(z_coords))
            }
        except:
            return None

    def _apply_offset(self, bbox, offset=(0, 0, 0)):
        """Applique un offset a une bbox.
        Note: ifcopenshell.geom retourne deja les coords en metres,
        donc pas besoin de facteur d'echelle sur la geometrie."""
        return {
            'min': (
                bbox['min'][0] + offset[0],
                bbox['min'][1] + offset[1],
                bbox['min'][2] + offset[2]
            ),
            'max': (
                bbox['max'][0] + offset[0],
                bbox['max'][1] + offset[1],
                bbox['max'][2] + offset[2]
            )
        }

    def _parse_space(self, space, source_file) -> Optional[Dict]:
        """Parse un IfcSpace"""
        try:
            name = space.Name or f"Space_{space.GlobalId[:8]}"
            long_name = getattr(space, 'LongName', None) or ""
            description = getattr(space, 'Description', None) or ""
            object_type = getattr(space, 'ObjectType', None) or ""

            bbox_raw = self._get_bounding_box(space, source_file)
            if not bbox_raw:
                return None

            # ifcopenshell.geom retourne deja en metres, pas besoin de scale
            bbox = bbox_raw

            volume = GeometryUtils.calculate_bounding_box_volume(bbox['min'], bbox['max'])

            return {
                "global_id": space.GlobalId,
                "name": name,
                "long_name": long_name,
                "description": description,
                "object_type": object_type,
                "predefined_type": str(getattr(space, 'PredefinedType', '') or ""),
                "ifc_type": space.is_a(),
                "bbox_min": bbox['min'],
                "bbox_max": bbox['max'],
                "centroid": GeometryUtils.get_centroid(bbox['min'], bbox['max']),
                "volume_m3": round(volume, 2),
                "floor_area_m2": round(GeometryUtils.calculate_floor_area(bbox['min'], bbox['max']), 2),
                "height_m": round(GeometryUtils.get_height(bbox['min'], bbox['max']), 2),
                "properties": self._get_element_properties(space)
            }
        except:
            return None

    def _parse_equipment(self, equipment, source_file) -> Optional[Dict]:
        """Parse un equipement"""
        try:
            name = equipment.Name or f"Equipment_{equipment.GlobalId[:8]}"

            bbox_raw = self._get_bounding_box(equipment, source_file)
            if not bbox_raw:
                return None

            # ifcopenshell.geom retourne deja en metres
            # Appliquer seulement l'offset d'alignement si fichier ELEC
            offset = self.offset_elec if source_file == self.ifc_file_elec else (0, 0, 0)
            bbox = self._apply_offset(bbox_raw, offset)

            max_dim = GeometryUtils.get_max_dimension(bbox['min'], bbox['max'])
            diagonal = GeometryUtils.get_diagonal_dimension(bbox['min'], bbox['max'])

            properties = self._get_element_properties(equipment)
            weight_kg = self._extract_weight(properties)

            return {
                "global_id": equipment.GlobalId,
                "name": name,
                "ifc_type": equipment.is_a(),
                "bbox_min": bbox['min'],
                "bbox_max": bbox['max'],
                "centroid": GeometryUtils.get_centroid(bbox['min'], bbox['max']),
                "max_dimension_m": round(max_dim, 3),
                "diagonal_dimension_m": round(diagonal, 3),
                "weight_kg": weight_kg,
                "properties": properties
            }
        except:
            return None

    def _parse_door(self, door, source_file) -> Optional[Dict]:
        """Parse une porte"""
        try:
            name = door.Name or f"Door_{door.GlobalId[:8]}"

            properties = self._get_element_properties(door)
            width = self._extract_door_width(door, properties)
            height = self._extract_door_height(door, properties)

            bbox_raw = self._get_bounding_box(door, source_file)
            if not bbox_raw:
                return None

            # ifcopenshell.geom retourne deja en metres
            bbox = bbox_raw

            return {
                "global_id": door.GlobalId,
                "name": name,
                "ifc_type": door.is_a(),
                "width_m": round(width, 3),
                "height_m": round(height, 3),
                "bbox_min": bbox['min'],
                "bbox_max": bbox['max'],
                "centroid": GeometryUtils.get_centroid(bbox['min'], bbox['max']),
                "properties": properties
            }
        except:
            return None

    def _parse_slab(self, slab, source_file) -> Optional[Dict]:
        """Parse une dalle"""
        try:
            name = slab.Name or f"Slab_{slab.GlobalId[:8]}"

            bbox_raw = self._get_bounding_box(slab, source_file)
            if not bbox_raw:
                return None

            # ifcopenshell.geom retourne deja en metres
            bbox = bbox_raw

            properties = self._get_element_properties(slab)
            load_capacity = self._extract_load_capacity(properties)

            return {
                "global_id": slab.GlobalId,
                "name": name,
                "ifc_type": slab.is_a(),
                "bbox_min": bbox['min'],
                "bbox_max": bbox['max'],
                "centroid": GeometryUtils.get_centroid(bbox['min'], bbox['max']),
                "load_capacity_kg": load_capacity,
                "properties": properties
            }
        except:
            return None

    # === EXTRACTION PROPRIETES ===

    def _get_element_properties(self, element) -> Dict:
        """Extrait proprietes"""
        properties = {}
        try:
            if hasattr(element, 'IsDefinedBy'):
                for definition in element.IsDefinedBy:
                    if definition.is_a('IfcRelDefinesByProperties'):
                        pset = definition.RelatingPropertyDefinition
                        if pset.is_a('IfcPropertySet'):
                            for prop in pset.HasProperties:
                                if prop.is_a('IfcPropertySingleValue'):
                                    properties[prop.Name] = str(prop.NominalValue.wrappedValue) if prop.NominalValue else None
        except:
            pass
        return properties

    def _extract_weight(self, properties: Dict) -> Optional[float]:
        """Extrait poids"""
        for key in ['Poids', 'Weight', 'Mass', 'Masse']:
            if key in properties:
                try:
                    return float(properties[key])
                except:
                    pass
        return None

    def _extract_door_width(self, door, properties: Dict) -> float:
        """Extrait largeur porte en metres"""
        # Depuis proprietes
        for key in ['Width', 'Largeur', 'OverallWidth']:
            if key in properties:
                try:
                    val = float(properties[key])
                    # Convertir si en cm
                    return val * self.unit_scale_archi
                except:
                    pass
        # Depuis attribut IFC
        try:
            if hasattr(door, 'OverallWidth') and door.OverallWidth:
                return float(door.OverallWidth) * self.unit_scale_archi
        except:
            pass
        return 0.9  # Valeur par defaut en m

    def _extract_door_height(self, door, properties: Dict) -> float:
        """Extrait hauteur porte en metres"""
        for key in ['Height', 'Hauteur', 'OverallHeight']:
            if key in properties:
                try:
                    val = float(properties[key])
                    return val * self.unit_scale_archi
                except:
                    pass
        try:
            if hasattr(door, 'OverallHeight') and door.OverallHeight:
                return float(door.OverallHeight) * self.unit_scale_archi
        except:
            pass
        return 2.1  # Valeur par defaut en m

    def _extract_load_capacity(self, properties: Dict) -> Optional[float]:
        """Extrait capacite charge dalle"""
        for key in ['LoadCapacity', 'ChargeAdmissible', 'MaxLoad']:
            if key in properties:
                try:
                    return float(properties[key])
                except:
                    pass
        return None
