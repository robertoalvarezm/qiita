# -----------------------------------------------------------------------------
# Copyright (c) 2014--, The Qiita Development Team.
#
# Distributed under the terms of the BSD 3-clause License.
#
# The full license is in the file LICENSE, distributed with this software.
# -----------------------------------------------------------------------------

from operator import itemgetter
from os.path import basename
from collections import defaultdict

from future.utils import viewitems

from qiita_db.util import (get_filetypes, get_files_from_uploads_folders,
                           get_data_types, convert_to_id, get_filepath_types)
from qiita_db.study import Study
from qiita_db.data import RawData
from qiita_db.ontology import Ontology
from qiita_db.metadata_template import PrepTemplate
from qiita_db.parameters import (Preprocessed454Params,
                                 PreprocessedIlluminaParams)
from qiita_pet.util import STATUS_STYLER
from qiita_pet.handlers.util import download_link_or_path
from .base_uimodule import BaseUIModule


filepath_types = [k.split('_', 1)[1].replace('_', ' ')
                  for k in get_filepath_types()
                  if k.startswith('raw_')]
fp_type_by_ft = defaultdict(
    lambda: filepath_types, SFF=['sff'], FASTA=['fasta', 'qual'],
    FASTQ=['barcodes', 'forward seqs', 'reverse seqs'])


def get_accessible_raw_data(user):
    """Retrieves a tuple of raw_data_id and the last study title for that
    raw_data
    """
    d = {}
    for sid in user.user_studies:
        for rdid in Study(sid).raw_data():
            d[int(rdid)] = Study(RawData(rdid).studies[-1]).title
    return d


def get_raw_data(rdis):
    """Get all raw data objects from a list of raw_data_ids"""
    return [RawData(rdi) for rdi in rdis]


def get_prep_templates(pt_ids):
    """Get all the prep template objects from a list of ids

    Parameters
    ----------
    pt_ids : list of int
        The prep template ids

    Returns
    -------
    list of PrepTemplate
    """
    return [PrepTemplate(pt_id) for pt_id in sorted(pt_ids)]


class PrepTemplateTab(BaseUIModule):
    def render(self, study, full_access):
        files = [f for _, f in get_files_from_uploads_folders(str(study.id))]
        data_types = sorted(viewitems(get_data_types()), key=itemgetter(1))
        prep_templates_info = [
            (pt.id, pt.data_type(), pt, STATUS_STYLER[pt.status])
            for pt in get_prep_templates(study.prep_templates())
            if full_access or pt.status() == 'public']
        # Get all the ENA terms for the investigation type
        ontology = Ontology(convert_to_id('ENA', 'ontology'))
        # make "Other" show at the bottom of the drop down menu
        ena_terms = []
        for v in sorted(ontology.terms):
            if v != 'Other':
                ena_terms.append('<option value="%s">%s</option>' % (v, v))
        ena_terms.append('<option value="Other">Other</option>')

        # New Type is for users to add a new user-defined investigation type
        user_defined_terms = ontology.user_defined_terms + ['New Type']

        return self.render_string(
            "study_description_templates/prep_template_tab.html",
            files=files,
            data_types=data_types,
            available_prep_templates=prep_templates_info,
            ena_terms=ena_terms,
            user_defined_terms=user_defined_terms,
            study=study,
            full_access=full_access)


class PrepTemplateInfoTab(BaseUIModule):
    def render(self, study, prep_template, full_access, ena_terms,
               user_defined_terms):
        user = self.current_user
        is_local_request = self._is_local()

        template_fps = []
        qiime_fps = []
        # Unfortunately, both the prep template and the qiime mapping files
        # have the sample type. The way to differentiate them is if we have
        # the substring 'qiime' in the basename
        for id_, fp in prep_template.get_filepaths():
            if 'qiime' in basename(fp):
                qiime_fps.append(
                    download_link_or_path(
                        is_local_request, fp, id_, 'Qiime mapping'))
            else:
                template_fps.append(
                    download_link_or_path(
                        is_local_request, fp, id_, 'Prep template'))

        # Since get_filepaths returns the paths sorted from newest to oldest,
        # the first in both list is the latest one
        current_template_fp = template_fps[0]
        current_qiime_fp = qiime_fps[0]

        if len(template_fps) > 1:
            show_old_templates = True
            old_templates = template_fps[1:]
        else:
            show_old_templates = False
            old_templates = None

        if len(qiime_fps) > 1:
            show_old_qiime_fps = True
            old_qiime_fps = qiime_fps[1:]
        else:
            show_old_qiime_fps = False
            old_qiime_fps = None

        filetypes = sorted(
            ((ft, ft_id, fp_type_by_ft[ft])
             for ft, ft_id in viewitems(get_filetypes())),
            key=itemgetter(1))
        files = [f for _, f in get_files_from_uploads_folders(str(study.id))]

        other_studies_rd = sorted(viewitems(
            get_accessible_raw_data(user)))

        # A prep template can be modified if it's status is sanbdox
        is_editable = prep_template.status == 'sanbdox'

        raw_data = prep_template.raw_data
        if raw_data:

            rd_ft = RawData(raw_data).filetype
            # If the prep template has a raw data associated, it can be
            # preprocessed. Retrieve the pre-processing parameters
            if rd_ft in ('SFF', 'FASTA'):
                param_iter = Preprocessed454Params.iter()
            elif rd_ft == 'FASTQ':
                param_iter = PreprocessedIlluminaParams.iter()
            else:
                raise NotImplementedError(
                    "Pre-processing of %s files currently not supported."
                    % rd_ft)

            preprocess_options = []
            for param in param_iter:
                text = ("<b>%s:</b> %s" % (k, v)
                        for k, v in viewitems(param.values))
                preprocess_options.append((param.id,
                                           param.name,
                                           '<br>'.join(text)))
            preprocessed_data = prep_template.preprocessed_data
        else:
            preprocess_options = []
            preprocessed_data = None

        preprocessing_status = prep_template.preprocessing_status

        return self.render_string(
            "study_description_templates/prep_template_info_tab.html",
            pt_id=prep_template.id,
            study_id=study.id,
            raw_data=raw_data,
            current_template_fp=current_template_fp,
            current_qiime_fp=current_qiime_fp,
            show_old_templates=show_old_templates,
            old_templates=old_templates,
            show_old_qiime_fps=show_old_qiime_fps,
            old_qiime_fps=old_qiime_fps,
            filetypes=filetypes,
            files=files,
            other_studies_rd=other_studies_rd,
            prep_template=prep_template,
            study=study,
            ena_terms=ena_terms,
            user_defined_terms=user_defined_terms,
            investigation_type=prep_template.investigation_type,
            is_editable=is_editable,
            preprocess_options=preprocess_options,
            preprocessed_data=preprocessed_data,
            preprocessing_status=preprocessing_status)


class RawDataInfoDiv(BaseUIModule):
    def render(self, raw_data_id, prep_template, study, files):
        rd = RawData(raw_data_id)
        raw_data_files = [(basename(fp), fp_type[4:])
                          for _, fp, fp_type in rd.get_filepaths()]
        filetype = rd.filetype
        fp_types = fp_type_by_ft[filetype]
        raw_data_link_status = rd.link_filepaths_status

        show_buttons = rd.status(study) == 'sandbox'
        link_msg = ""
        if show_buttons:
            # Define the message for the link status
            if raw_data_link_status == 'linking':
                link_msg = "Linking files..."
                show_buttons = False
            elif raw_data_link_status == 'unlinking':
                link_msg = "Unlinking files..."
                show_buttons = False
            elif raw_data_link_status.startswith('failed'):
                link_msg = "Error (un)linking files: %s" % raw_data_link_status

        return self.render_string(
            "study_description_templates/raw_data_info.html",
            rd_id=raw_data_id,
            rd_filetype=rd.filetype,
            raw_data_files=raw_data_files,
            prep_template_id=prep_template.id,
            files=files,
            filepath_types=fp_types,
            filetype=filetype,
            link_msg="",
            show_buttons=show_buttons)


class EditInvestigationType(BaseUIModule):
    def render(self, ena_terms, user_defined_terms, prep_id, inv_type, ppd_id):
        return self.render_string(
            "study_description_templates/edit_investigation_type.html",
            ena_terms=ena_terms,
            user_defined_terms=user_defined_terms,
            prep_id=prep_id,
            investigation_type=inv_type,
            ppd_id=ppd_id)
