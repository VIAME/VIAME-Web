import re
from pathlib import Path
from typing import Dict, List, Optional

from dive_utils.types import (
    AvailableJobSchema,
    PipelineCategory,
    PipelineDescription,
    TrainingConfigurationSummary,
)

DefaultTrainingConfiguration = "train_detector_default.viame_csv.conf"
AllowedTrainingConfigs = r".*\.viame_csv\.conf$"
DisallowedTrainingConfigs = r".*_nf\.viame_csv\.conf$"
AllowedStaticPipelines = (
    r"^detector_.+|^tracker_.+|^utility_.+|^generate_.+|^measurement_gmm_.+"
)
DisallowedStaticPipelines = (
    # Remove utilities pipes which hold no meaning in web
    r".*local.*|"
    r".*hough.*|"
    r".*_svm_models\.pipe|"
    r"detector_extract_chips\.pipe|"
    # Remove tracker pipelines which hold no meaning in web
    r"tracker_stabilized_iou\.pipe|"
    r"tracker_short_term\.pipe|"
    # Remove seal and sea lion specialized pipelines un-runnable in web
    r"detector_arctic_.*fusion.*\.pipe|"
    r".*[2|3]-cam\.pipe"
)


def load_static_pipelines(search_path: Path) -> Dict[str, PipelineCategory]:
    pipedict: Dict[str, PipelineCategory] = {}

    pipelist = [
        path.name
        for path in search_path.glob("./*.pipe")
        if re.match(AllowedStaticPipelines, path.name)
        and not re.match(DisallowedStaticPipelines, path.name)
    ]

    for pipe in pipelist:
        pipe_type, *nameparts = pipe.replace(".pipe", "").split("_")
        pipe_info: PipelineDescription = {
            "name": " ".join(nameparts),
            "type": pipe_type,
            "pipe": pipe,
            "folderId": None,
        }
        print(f"Discovered pipe {pipe_info}")
        if pipe_type in pipedict:
            pipedict[pipe_type]["pipes"].append(pipe_info)
        else:
            pipedict[pipe_type] = {"pipes": [pipe_info], "description": ""}

    return pipedict


def load_training_configurations(search_path: Path) -> TrainingConfigurationSummary:
    configurations: List[str] = []
    default_config: Optional[str] = None

    for pipe in search_path.glob("./*.conf"):
        pipe_name = pipe.name
        configurations.append(pipe_name)
        print(f"Discovered training {pipe_name}")
        if pipe_name == DefaultTrainingConfiguration:
            default_config = pipe_name

    # Filter out stuff that doesn't match allowed patterns
    configurations = [
        c
        for c in configurations
        if re.match(AllowedTrainingConfigs, c)
        and not re.match(DisallowedTrainingConfigs, c)
    ]

    return {
        "configs": configurations,
        "default": default_config or pipe_name,
    }


def discover_configs(search_path: Path) -> AvailableJobSchema:
    return {
        'pipelines': load_static_pipelines(search_path),
        'training': load_training_configurations(search_path),
    }
