using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Autodesk.Revit.DB.Electrical;
using Autodesk.Revit.DB.Mechanical;

namespace CHU_SecurityAnalyzer.Core
{
    /// <summary>
    /// Extrait les données BIM depuis les maquettes Revit (ARCHI hôte + ELEC liée).
    /// Produit un ExtractedData compatible avec le format JSON du Python IFCExtractor.
    ///
    /// IMPORTANT - Unités :
    /// - Revit stocke en pieds (feet) en interne
    /// - On convertit tout en mètres pour le Python (1 foot = 0.3048 m)
    /// - Les Shared Coordinates sont utilisées (les 2 maquettes sont coordonnées)
    /// </summary>
    public class BIMDataExtractor
    {
        private const double FEET_TO_METERS = 0.3048;

        private readonly Document _docArchi;
        private readonly Document _docElec;

        public BIMDataExtractor(Document docArchi, Document docElec = null)
        {
            _docArchi = docArchi ?? throw new ArgumentNullException(nameof(docArchi));
            _docElec = docElec;
        }

        /// <summary>
        /// Extraction complète - équivalent de IFCExtractor.extract_all()
        /// </summary>
        public ExtractedData ExtractAll()
        {
            var data = new ExtractedData();

            data.Spaces = ExtractSpaces();
            data.Equipment = ExtractEquipment();
            data.Doors = ExtractDoors();
            data.Slabs = ExtractSlabs();

            data.Summary = new SummaryData
            {
                Spaces = data.Spaces.Count,
                Equipment = data.Equipment.Count,
                Doors = data.Doors.Count,
                Slabs = data.Slabs.Count
            };

            return data;
        }

        // =====================================================================
        //  EXTRACTION SPACES (Rooms depuis maquette ARCHI)
        // =====================================================================

        public List<SpaceData> ExtractSpaces()
        {
            var spaces = new List<SpaceData>();

            // Récupérer les Rooms de la maquette ARCHI
            var collector = new FilteredElementCollector(_docArchi)
                .OfCategory(BuiltInCategory.OST_Rooms)
                .WhereElementIsNotElementType();

            foreach (Element elem in collector)
            {
                if (!(elem is Room room)) continue;
                if (room.Area <= 0) continue; // Ignorer rooms non placées

                try
                {
                    var spaceData = ParseRoom(room);
                    if (spaceData != null)
                        spaces.Add(spaceData);
                }
                catch { /* Ignorer erreurs individuelles */ }
            }

            return spaces;
        }

        private SpaceData ParseRoom(Room room)
        {
            // Bounding box en Shared Coordinates
            BoundingBoxXYZ bbox = room.get_BoundingBox(null);
            if (bbox == null) return null;

            // Convertir feet -> metres
            double[] bboxMin = FeetToMeters(bbox.Min);
            double[] bboxMax = FeetToMeters(bbox.Max);
            double[] centroid = GetCentroid(bboxMin, bboxMax);

            double height = bboxMax[2] - bboxMin[2];
            double area = room.Area * FEET_TO_METERS * FEET_TO_METERS; // sq feet -> sq meters
            double volume = room.Volume * Math.Pow(FEET_TO_METERS, 3);

            // LongName : dans Revit, c'est souvent le paramètre "Name" ou un shared parameter
            string longName = GetParamValue(room, "LongName")
                           ?? GetParamValue(room, "Long Name")
                           ?? room.get_Parameter(BuiltInParameter.ROOM_NAME)?.AsString()
                           ?? "";

            return new SpaceData
            {
                GlobalId = room.UniqueId,
                Name = room.Number ?? $"Room_{room.Id.IntegerValue}",
                LongName = longName,
                Description = GetParamValue(room, "Description") ?? "",
                ObjectType = room.GetType().Name,
                PredefinedType = "",
                IfcType = "IfcSpace",
                BboxMin = bboxMin,
                BboxMax = bboxMax,
                Centroid = centroid,
                VolumeM3 = Math.Round(volume, 2),
                FloorAreaM2 = Math.Round(area, 2),
                HeightM = Math.Round(height, 2),
                Properties = GetElementProperties(room),
                RevitElementId = room.Id.IntegerValue
            };
        }

        // =====================================================================
        //  EXTRACTION EQUIPMENT (depuis maquette ELEC liée)
        // =====================================================================

        public List<EquipmentData> ExtractEquipment()
        {
            var equipment = new List<EquipmentData>();

            // Source : maquette ELEC si disponible, sinon ARCHI
            Document sourceDoc = _docElec ?? _docArchi;

            // Catégories d'équipements électriques
            var categories = new[]
            {
                BuiltInCategory.OST_ElectricalEquipment,
                BuiltInCategory.OST_ElectricalFixtures,
                BuiltInCategory.OST_LightingFixtures,
                BuiltInCategory.OST_LightingDevices,
                BuiltInCategory.OST_CableTray,
                BuiltInCategory.OST_Conduit,
                BuiltInCategory.OST_CommunicationDevices,
                BuiltInCategory.OST_DataDevices,
                BuiltInCategory.OST_FireAlarmDevices,
                BuiltInCategory.OST_SecurityDevices
            };

            foreach (var cat in categories)
            {
                try
                {
                    var collector = new FilteredElementCollector(sourceDoc)
                        .OfCategory(cat)
                        .WhereElementIsNotElementType();

                    foreach (Element elem in collector)
                    {
                        try
                        {
                            var eqData = ParseEquipment(elem, sourceDoc);
                            if (eqData != null)
                                equipment.Add(eqData);
                        }
                        catch { }
                    }
                }
                catch { }
            }

            // Si ELEC est un lien, chercher aussi dans les RevitLinkInstances
            if (_docElec == null)
            {
                equipment.AddRange(ExtractEquipmentFromLinks(categories));
            }

            return equipment;
        }

        private List<EquipmentData> ExtractEquipmentFromLinks(BuiltInCategory[] categories)
        {
            var equipment = new List<EquipmentData>();

            var links = new FilteredElementCollector(_docArchi)
                .OfClass(typeof(RevitLinkInstance));

            foreach (RevitLinkInstance link in links)
            {
                Document linkDoc = link.GetLinkDocument();
                if (linkDoc == null) continue;

                string linkName = linkDoc.Title.ToLower();
                if (!linkName.Contains("elec")) continue;

                // Transformation du lien (Shared Coordinates)
                Transform linkTransform = link.GetTotalTransform();

                foreach (var cat in categories)
                {
                    try
                    {
                        var collector = new FilteredElementCollector(linkDoc)
                            .OfCategory(cat)
                            .WhereElementIsNotElementType();

                        foreach (Element elem in collector)
                        {
                            try
                            {
                                var eqData = ParseEquipmentFromLink(elem, linkDoc, linkTransform);
                                if (eqData != null)
                                    equipment.Add(eqData);
                            }
                            catch { }
                        }
                    }
                    catch { }
                }
            }

            return equipment;
        }

        private EquipmentData ParseEquipment(Element elem, Document doc)
        {
            BoundingBoxXYZ bbox = elem.get_BoundingBox(null);
            if (bbox == null) return null;

            double[] bboxMin = FeetToMeters(bbox.Min);
            double[] bboxMax = FeetToMeters(bbox.Max);
            double[] centroid = GetCentroid(bboxMin, bboxMax);

            double maxDim = GetMaxDimension(bboxMin, bboxMax);
            double diagonal = GetDiagonal(bboxMin, bboxMax);

            var properties = GetElementProperties(elem);
            double? weight = ExtractWeight(properties);

            return new EquipmentData
            {
                GlobalId = elem.UniqueId,
                Name = elem.Name ?? $"Equipment_{elem.Id.IntegerValue}",
                IfcType = MapRevitCategoryToIfc(elem.Category),
                BboxMin = bboxMin,
                BboxMax = bboxMax,
                Centroid = centroid,
                MaxDimensionM = Math.Round(maxDim, 3),
                DiagonalDimensionM = Math.Round(diagonal, 3),
                WeightKg = weight,
                Properties = properties,
                RevitElementId = elem.Id.IntegerValue
            };
        }

        private EquipmentData ParseEquipmentFromLink(Element elem, Document linkDoc, Transform transform)
        {
            BoundingBoxXYZ bbox = elem.get_BoundingBox(null);
            if (bbox == null) return null;

            // Appliquer la transformation du lien (Shared Coordinates)
            XYZ minPt = transform.OfPoint(bbox.Min);
            XYZ maxPt = transform.OfPoint(bbox.Max);

            double[] bboxMin = FeetToMeters(minPt);
            double[] bboxMax = FeetToMeters(maxPt);

            // Corriger si min > max après transformation
            for (int i = 0; i < 3; i++)
            {
                if (bboxMin[i] > bboxMax[i])
                {
                    double tmp = bboxMin[i];
                    bboxMin[i] = bboxMax[i];
                    bboxMax[i] = tmp;
                }
            }

            double[] centroid = GetCentroid(bboxMin, bboxMax);
            double maxDim = GetMaxDimension(bboxMin, bboxMax);
            double diagonal = GetDiagonal(bboxMin, bboxMax);

            var properties = GetElementProperties(elem);
            double? weight = ExtractWeight(properties);

            return new EquipmentData
            {
                GlobalId = elem.UniqueId,
                Name = elem.Name ?? $"Equipment_{elem.Id.IntegerValue}",
                IfcType = MapRevitCategoryToIfc(elem.Category),
                BboxMin = bboxMin,
                BboxMax = bboxMax,
                Centroid = centroid,
                MaxDimensionM = Math.Round(maxDim, 3),
                DiagonalDimensionM = Math.Round(diagonal, 3),
                WeightKg = weight,
                Properties = properties,
                RevitElementId = elem.Id.IntegerValue
            };
        }

        // =====================================================================
        //  EXTRACTION DOORS (depuis maquette ARCHI)
        // =====================================================================

        public List<DoorData> ExtractDoors()
        {
            var doors = new List<DoorData>();

            var collector = new FilteredElementCollector(_docArchi)
                .OfCategory(BuiltInCategory.OST_Doors)
                .WhereElementIsNotElementType();

            foreach (Element elem in collector)
            {
                if (!(elem is FamilyInstance door)) continue;

                try
                {
                    var doorData = ParseDoor(door);
                    if (doorData != null)
                        doors.Add(doorData);
                }
                catch { }
            }

            return doors;
        }

        private DoorData ParseDoor(FamilyInstance door)
        {
            BoundingBoxXYZ bbox = door.get_BoundingBox(null);
            if (bbox == null) return null;

            double[] bboxMin = FeetToMeters(bbox.Min);
            double[] bboxMax = FeetToMeters(bbox.Max);
            double[] centroid = GetCentroid(bboxMin, bboxMax);

            // Largeur et hauteur depuis les paramètres type
            double width = GetDoorDimension(door, "Width", "Largeur",
                BuiltInParameter.DOOR_WIDTH, BuiltInParameter.FAMILY_WIDTH_PARAM);
            double height = GetDoorDimension(door, "Height", "Hauteur",
                BuiltInParameter.DOOR_HEIGHT, BuiltInParameter.FAMILY_HEIGHT_PARAM);

            // Fallback : dimensions depuis bbox
            if (width <= 0) width = Math.Abs(bboxMax[0] - bboxMin[0]);
            if (height <= 0) height = Math.Abs(bboxMax[2] - bboxMin[2]);
            // Prendre le min des deux côtés XY comme largeur si la porte est tournée
            if (width <= 0)
            {
                double dx = Math.Abs(bboxMax[0] - bboxMin[0]);
                double dy = Math.Abs(bboxMax[1] - bboxMin[1]);
                width = Math.Min(dx, dy);
            }

            return new DoorData
            {
                GlobalId = door.UniqueId,
                Name = door.Name ?? $"Door_{door.Id.IntegerValue}",
                IfcType = "IfcDoor",
                WidthM = Math.Round(width, 3),
                HeightM = Math.Round(height, 3),
                BboxMin = bboxMin,
                BboxMax = bboxMax,
                Centroid = centroid,
                Properties = GetElementProperties(door),
                RevitElementId = door.Id.IntegerValue
            };
        }

        private double GetDoorDimension(FamilyInstance door, string paramName1, string paramName2,
            BuiltInParameter bip1, BuiltInParameter bip2)
        {
            // Paramètre instance (AsDouble = pieds internes Revit)
            foreach (string pName in new[] { paramName1, paramName2 })
            {
                Parameter param = door.LookupParameter(pName);
                if (param != null && param.HasValue && param.StorageType == StorageType.Double)
                {
                    double v = param.AsDouble();
                    if (v > 0) return v * FEET_TO_METERS;
                }
            }

            // BuiltInParameter
            foreach (var bip in new[] { bip1, bip2 })
            {
                Parameter p = door.get_Parameter(bip);
                if (p != null && p.HasValue)
                    return p.AsDouble() * FEET_TO_METERS;
            }

            // Type parameters
            ElementId typeId = door.GetTypeId();
            if (typeId != ElementId.InvalidElementId)
            {
                Element doorType = _docArchi.GetElement(typeId);
                if (doorType != null)
                {
                    foreach (string pName in new[] { paramName1, paramName2 })
                    {
                        Parameter param = doorType.LookupParameter(pName);
                        if (param != null && param.HasValue && param.StorageType == StorageType.Double)
                        {
                            double v = param.AsDouble();
                            if (v > 0) return v * FEET_TO_METERS;
                        }
                    }
                    foreach (var bip in new[] { bip1, bip2 })
                    {
                        Parameter p = doorType.get_Parameter(bip);
                        if (p != null && p.HasValue)
                            return p.AsDouble() * FEET_TO_METERS;
                    }
                }
            }

            return 0;
        }

        // =====================================================================
        //  EXTRACTION SLABS (Floors depuis maquette ARCHI)
        // =====================================================================

        public List<SlabData> ExtractSlabs()
        {
            var slabs = new List<SlabData>();

            var collector = new FilteredElementCollector(_docArchi)
                .OfCategory(BuiltInCategory.OST_Floors)
                .WhereElementIsNotElementType();

            foreach (Element elem in collector)
            {
                try
                {
                    var slabData = ParseSlab(elem);
                    if (slabData != null)
                        slabs.Add(slabData);
                }
                catch { }
            }

            return slabs;
        }

        private SlabData ParseSlab(Element slab)
        {
            BoundingBoxXYZ bbox = slab.get_BoundingBox(null);
            if (bbox == null) return null;

            double[] bboxMin = FeetToMeters(bbox.Min);
            double[] bboxMax = FeetToMeters(bbox.Max);
            double[] centroid = GetCentroid(bboxMin, bboxMax);

            var properties = GetElementProperties(slab);
            double? loadCapacity = ExtractLoadCapacity(properties);

            return new SlabData
            {
                GlobalId = slab.UniqueId,
                Name = slab.Name ?? $"Slab_{slab.Id.IntegerValue}",
                IfcType = "IfcSlab",
                BboxMin = bboxMin,
                BboxMax = bboxMax,
                Centroid = centroid,
                LoadCapacityKg = loadCapacity,
                Properties = properties,
                RevitElementId = slab.Id.IntegerValue
            };
        }

        // =====================================================================
        //  UTILITAIRES
        // =====================================================================

        private double[] FeetToMeters(XYZ point)
        {
            return new[]
            {
                point.X * FEET_TO_METERS,
                point.Y * FEET_TO_METERS,
                point.Z * FEET_TO_METERS
            };
        }

        private double[] GetCentroid(double[] min, double[] max)
        {
            return new[]
            {
                (min[0] + max[0]) / 2.0,
                (min[1] + max[1]) / 2.0,
                (min[2] + max[2]) / 2.0
            };
        }

        private double GetMaxDimension(double[] min, double[] max)
        {
            double dx = Math.Abs(max[0] - min[0]);
            double dy = Math.Abs(max[1] - min[1]);
            double dz = Math.Abs(max[2] - min[2]);
            return Math.Max(dx, Math.Max(dy, dz));
        }

        private double GetDiagonal(double[] min, double[] max)
        {
            double dx = max[0] - min[0];
            double dy = max[1] - min[1];
            double dz = max[2] - min[2];
            return Math.Sqrt(dx * dx + dy * dy + dz * dz);
        }

        private Dictionary<string, string> GetElementProperties(Element elem)
        {
            var props = new Dictionary<string, string>();

            foreach (Parameter param in elem.Parameters)
            {
                if (!param.HasValue) continue;
                string name = param.Definition.Name;
                string value = null;

                switch (param.StorageType)
                {
                    case StorageType.String:
                        value = param.AsString();
                        break;
                    case StorageType.Double:
                        value = param.AsDouble().ToString("F4");
                        break;
                    case StorageType.Integer:
                        value = param.AsInteger().ToString();
                        break;
                    case StorageType.ElementId:
                        value = param.AsElementId().IntegerValue.ToString();
                        break;
                }

                if (!string.IsNullOrEmpty(value) && !props.ContainsKey(name))
                    props[name] = value;
            }

            return props;
        }

        private string GetParamValue(Element elem, string paramName)
        {
            Parameter param = elem.LookupParameter(paramName);
            if (param != null && param.HasValue)
            {
                if (param.StorageType == StorageType.String)
                    return param.AsString();
                return param.AsValueString();
            }
            return null;
        }

        private double? ExtractWeight(Dictionary<string, string> properties)
        {
            foreach (string key in new[] { "Poids", "Weight", "Mass", "Masse" })
            {
                if (properties.ContainsKey(key))
                {
                    if (double.TryParse(properties[key], out double val))
                        return val;
                }
            }
            return null;
        }

        private double? ExtractLoadCapacity(Dictionary<string, string> properties)
        {
            foreach (string key in new[] { "LoadCapacity", "ChargeAdmissible", "MaxLoad" })
            {
                if (properties.ContainsKey(key))
                {
                    if (double.TryParse(properties[key], out double val))
                        return val;
                }
            }
            return null;
        }

        private string MapRevitCategoryToIfc(Category cat)
        {
            if (cat == null) return "IfcBuildingElementProxy";

            switch ((BuiltInCategory)cat.Id.IntegerValue)
            {
                case BuiltInCategory.OST_ElectricalEquipment:
                    return "IfcElectricDistributionBoard";
                case BuiltInCategory.OST_ElectricalFixtures:
                    return "IfcOutlet";
                case BuiltInCategory.OST_LightingFixtures:
                case BuiltInCategory.OST_LightingDevices:
                    return "IfcLightFixture";
                case BuiltInCategory.OST_CableTray:
                    return "IfcCableCarrierSegment";
                case BuiltInCategory.OST_Conduit:
                    return "IfcCableSegment";
                case BuiltInCategory.OST_CommunicationDevices:
                case BuiltInCategory.OST_DataDevices:
                    return "IfcCommunicationsAppliance";
                case BuiltInCategory.OST_FireAlarmDevices:
                    return "IfcAlarm";
                case BuiltInCategory.OST_SecurityDevices:
                    return "IfcSensor";
                default:
                    return "IfcBuildingElementProxy";
            }
        }
    }
}
