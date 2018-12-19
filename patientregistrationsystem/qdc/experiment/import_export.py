import os
import shutil
import tempfile
import zipfile
from os import path, mkdir

from django.conf import settings

from experiment.admin import ResearchProjectResource, ExperimentResource, GroupResource, ComponentResource,\
    ComponentConfigResource
from experiment.models import Group, ComponentConfiguration


class ExportExperiment:

    ZIP_FILE_NAME = 'experiment'
    MEDIA_SUBDIR = 'media'
    RESEARCH_PROJECT_CSV = 'research_project.csv'
    EXPERIMENT_CSV = 'experiment.csv'
    GROUPS_CSV = 'groups.csv'
    COMPONENTS_CSV = 'components.csv'
    COMPONENTS_CONFIG_CSV = 'componentsconfig.csv'

    def __init__(self, experiment):
        self.experiment = experiment
        self.temp_dir = tempfile.mkdtemp()
        self.temp_media_dir = path.join(self.temp_dir, self.MEDIA_SUBDIR)
        self.temp_dir_zip = tempfile.mkdtemp()
        mkdir(self.temp_media_dir)

    def __del__(self):
        shutil.rmtree(self.temp_dir)
        shutil.rmtree(self.temp_dir_zip)

    def copy_file(self, file_path):
        absolute_path = path.join(self.temp_media_dir, path.dirname(file_path))
        if not path.exists(absolute_path):
            os.makedirs(absolute_path)
        shutil.copy(path.join(settings.MEDIA_ROOT, file_path), absolute_path)

    def export_research_project(self):
        dataset = ResearchProjectResource().export(id=self.experiment.research_project.id)
        temp_filename = path.join(self.temp_dir, self.RESEARCH_PROJECT_CSV)
        with open(temp_filename, 'w') as f:
            f.write(dataset.csv)

    def export_experiment(self):
        dataset = ExperimentResource().export(id=self.experiment.id)
        # remove research_project from dataset;
        # it's included when importing (after creating it)
        # see that this is done because we can't include 'research_project' in exclude
        # Meta class attribute: fields listed there are considered both for export as
        # import
        del (dataset['research_project'])
        temp_filename = path.join(self.temp_dir, self.EXPERIMENT_CSV)
        with open(temp_filename, 'w') as f:
            f.write(dataset.csv)

        file_path = dataset['ethics_committee_project_file'][0]
        if file_path:
            self.copy_file(file_path)

    def export_groups(self):
        dataset = GroupResource().export(experiment=self.experiment)
        temp_filename = path.join(self.temp_dir, self.GROUPS_CSV)
        with open(temp_filename, 'w') as f:
            f.write(dataset.csv)

    def export_components(self):
        groups = Group.objects.filter(experiment=self.experiment)
        list_components_ids = []
        list_rootcomponents_ids = []
        for group in groups:
            rootcomponent_id = group.experimental_protocol_id
            list_components_ids.append(rootcomponent_id)
            list_rootcomponents_ids.append(rootcomponent_id)
            components = ComponentConfiguration.objects.filter(parent_id=rootcomponent_id)
            for component in components:
                list_components_ids.append(component.component_id)

        dataset_components = ComponentResource().export(ids=list_components_ids)
        temp_file = path.join(self.temp_dir, self.COMPONENTS_CSV)
        with open(temp_file, 'w') as f:
            f.write(dataset_components.csv)

        dataset_components_config = ComponentConfigResource().export(ids=list_rootcomponents_ids)
        temp_file = path.join(self.temp_dir, self.COMPONENTS_CONFIG_CSV)
        with open(temp_file, 'w') as f:
            f.write(dataset_components_config.csv)

    def export_all(self):
        self.export_research_project()
        self.export_experiment()
        self.export_groups()
        self.export_components()

        shutil.make_archive(path.join(self.temp_dir_zip, self.ZIP_FILE_NAME), 'zip', self.temp_dir)


class ImportExperiment:

    MEDIA_SUBDIR = 'media'
    RESEARCH_PROJECT_CSV = 'research_project.csv'
    BAD_ZIP_FILE = 1
    FILE_NOT_FOUND_ERROR = 2

    def __init__(self, file_path):
        self.file_path = file_path
        self.temp_dir = tempfile.mkdtemp()

    def __del__(self):
        shutil.rmtree(self.temp_dir)

    def import_all(self):
        try:
            zipfile.ZipFile(self.file_path)
        except zipfile.BadZipFile:
            return (
                self.BAD_ZIP_FILE, 'Not a zip file. Aborting import experiment.'
            )

        with zipfile.ZipFile(self.file_path) as f:
            f.extractall(self.temp_dir)
        try:
            open(path.join(self.temp_dir, self.RESEARCH_PROJECT_CSV))
        except FileNotFoundError:
            return (
                self.FILE_NOT_FOUND_ERROR, '%s not found in zip file. Aborting import experiment.'
                % self.RESEARCH_PROJECT_CSV
            )
