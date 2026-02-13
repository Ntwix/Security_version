using System;
using System.Collections.Generic;
using System.Runtime.Serialization;

namespace CHU_SecurityAnalyzer.Core
{
    /// <summary>
    /// Modèles de données compatibles avec le format JSON attendu par le Python.
    /// Le format reproduit exactement la sortie de IFCExtractor.extract_all()
    /// </summary>

    [DataContract]
    public class ExtractedData
    {
        [DataMember(Name = "spaces")]
        public List<SpaceData> Spaces { get; set; } = new List<SpaceData>();

        [DataMember(Name = "equipment")]
        public List<EquipmentData> Equipment { get; set; } = new List<EquipmentData>();

        [DataMember(Name = "doors")]
        public List<DoorData> Doors { get; set; } = new List<DoorData>();

        [DataMember(Name = "slabs")]
        public List<SlabData> Slabs { get; set; } = new List<SlabData>();

        [DataMember(Name = "summary")]
        public SummaryData Summary { get; set; } = new SummaryData();
    }

    [DataContract]
    public class SpaceData
    {
        [DataMember(Name = "global_id")]
        public string GlobalId { get; set; }

        [DataMember(Name = "name")]
        public string Name { get; set; }

        [DataMember(Name = "long_name")]
        public string LongName { get; set; }

        [DataMember(Name = "description")]
        public string Description { get; set; }

        [DataMember(Name = "object_type")]
        public string ObjectType { get; set; }

        [DataMember(Name = "predefined_type")]
        public string PredefinedType { get; set; }

        [DataMember(Name = "ifc_type")]
        public string IfcType { get; set; }

        [DataMember(Name = "bbox_min")]
        public double[] BboxMin { get; set; }

        [DataMember(Name = "bbox_max")]
        public double[] BboxMax { get; set; }

        [DataMember(Name = "centroid")]
        public double[] Centroid { get; set; }

        [DataMember(Name = "volume_m3")]
        public double VolumeM3 { get; set; }

        [DataMember(Name = "floor_area_m2")]
        public double FloorAreaM2 { get; set; }

        [DataMember(Name = "height_m")]
        public double HeightM { get; set; }

        [DataMember(Name = "properties")]
        public Dictionary<string, string> Properties { get; set; } = new Dictionary<string, string>();

        /// <summary>ElementId Revit pour la coloration</summary>
        [DataMember(Name = "revit_element_id")]
        public int RevitElementId { get; set; }
    }

    [DataContract]
    public class EquipmentData
    {
        [DataMember(Name = "global_id")]
        public string GlobalId { get; set; }

        [DataMember(Name = "name")]
        public string Name { get; set; }

        [DataMember(Name = "ifc_type")]
        public string IfcType { get; set; }

        [DataMember(Name = "bbox_min")]
        public double[] BboxMin { get; set; }

        [DataMember(Name = "bbox_max")]
        public double[] BboxMax { get; set; }

        [DataMember(Name = "centroid")]
        public double[] Centroid { get; set; }

        [DataMember(Name = "max_dimension_m")]
        public double MaxDimensionM { get; set; }

        [DataMember(Name = "diagonal_dimension_m")]
        public double DiagonalDimensionM { get; set; }

        [DataMember(Name = "weight_kg")]
        public double? WeightKg { get; set; }

        [DataMember(Name = "properties")]
        public Dictionary<string, string> Properties { get; set; } = new Dictionary<string, string>();

        [DataMember(Name = "revit_element_id")]
        public int RevitElementId { get; set; }
    }

    [DataContract]
    public class DoorData
    {
        [DataMember(Name = "global_id")]
        public string GlobalId { get; set; }

        [DataMember(Name = "name")]
        public string Name { get; set; }

        [DataMember(Name = "ifc_type")]
        public string IfcType { get; set; }

        [DataMember(Name = "width_m")]
        public double WidthM { get; set; }

        [DataMember(Name = "height_m")]
        public double HeightM { get; set; }

        [DataMember(Name = "bbox_min")]
        public double[] BboxMin { get; set; }

        [DataMember(Name = "bbox_max")]
        public double[] BboxMax { get; set; }

        [DataMember(Name = "centroid")]
        public double[] Centroid { get; set; }

        [DataMember(Name = "properties")]
        public Dictionary<string, string> Properties { get; set; } = new Dictionary<string, string>();

        [DataMember(Name = "revit_element_id")]
        public int RevitElementId { get; set; }
    }

    [DataContract]
    public class SlabData
    {
        [DataMember(Name = "global_id")]
        public string GlobalId { get; set; }

        [DataMember(Name = "name")]
        public string Name { get; set; }

        [DataMember(Name = "ifc_type")]
        public string IfcType { get; set; }

        [DataMember(Name = "bbox_min")]
        public double[] BboxMin { get; set; }

        [DataMember(Name = "bbox_max")]
        public double[] BboxMax { get; set; }

        [DataMember(Name = "centroid")]
        public double[] Centroid { get; set; }

        [DataMember(Name = "load_capacity_kg")]
        public double? LoadCapacityKg { get; set; }

        [DataMember(Name = "properties")]
        public Dictionary<string, string> Properties { get; set; } = new Dictionary<string, string>();

        [DataMember(Name = "revit_element_id")]
        public int RevitElementId { get; set; }
    }

    [DataContract]
    public class SummaryData
    {
        [DataMember(Name = "spaces")]
        public int Spaces { get; set; }

        [DataMember(Name = "equipment")]
        public int Equipment { get; set; }

        [DataMember(Name = "doors")]
        public int Doors { get; set; }

        [DataMember(Name = "slabs")]
        public int Slabs { get; set; }
    }

    // === Modèles pour les résultats d'analyse Python ===

    [DataContract]
    public class AnalysisResults
    {
        [DataMember(Name = "metadata")]
        public AnalysisMetadata Metadata { get; set; }

        [DataMember(Name = "violations")]
        public List<ViolationData> Violations { get; set; } = new List<ViolationData>();
    }

    [DataContract]
    public class AnalysisMetadata
    {
        [DataMember(Name = "timestamp")]
        public string Timestamp { get; set; }

        [DataMember(Name = "ifc_file")]
        public string IfcFile { get; set; }

        [DataMember(Name = "rules_analyzed")]
        public List<string> RulesAnalyzed { get; set; }

        [DataMember(Name = "statistics")]
        public AnalysisStatistics Statistics { get; set; }
    }

    [DataContract]
    public class AnalysisStatistics
    {
        [DataMember(Name = "total_violations")]
        public int TotalViolations { get; set; }

        [DataMember(Name = "critical")]
        public int Critical { get; set; }

        [DataMember(Name = "important")]
        public int Important { get; set; }

        [DataMember(Name = "by_rule")]
        public Dictionary<string, int> ByRule { get; set; }
    }

    [DataContract]
    public class ViolationData
    {
        [DataMember(Name = "rule_id")]
        public string RuleId { get; set; }

        [DataMember(Name = "severity")]
        public string Severity { get; set; }

        [DataMember(Name = "space_name")]
        public string SpaceName { get; set; }

        [DataMember(Name = "space_global_id")]
        public string SpaceGlobalId { get; set; }

        [DataMember(Name = "description")]
        public string Description { get; set; }

        [DataMember(Name = "location")]
        public double[] Location { get; set; }

        [DataMember(Name = "recommendation")]
        public string Recommendation { get; set; }
    }
}
