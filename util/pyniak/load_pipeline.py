__author__ = 'poquirion'

import shutil
import json
import os
import re
import subprocess
import tempfile

LOCAL_CONFIG_PATH = '/local_config'
PSOM_GB_LOCAL = "{}/../lib/psom_gb_vars_local.cbrain".format(os.path.dirname(os.path.realpath(__file__)))

try:
    import psutil
    psutil_loaded = True
except ImportError:
    psutil_loaded = False


def num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)

def string(s):
    """
    :param s: A PSOM option
    :return: The right cast for octave
    """
    s.replace("\\", '')
    s = re.match("[\'\"]?([\w+\ -]*)[\'\"]?", s).groups()[0]
    if s in ['true', 'false', 'Inf']:
        return "{0}".format(s)
    return "'{0}'".format(s)


class BasePipeline(object):
    """
    This is the base class to run PSOM/NIAK pipeline under CBRAIN and the
    BOUTIQUE interface.
    """

    BOUTIQUE_PATH = "{0}/boutique_descriptor"\
        .format(os.path.dirname(os.path.realpath(__file__)))
    BOUTIQUE_INPUTS = "inputs"
    BOUTIQUE_CMD_LINE = "command-line-flag"
    BOUTIQUE_TYPE_CAST = {"Number": num, "String": string, "File": string, "Flag": string}
    BOUTIQUE_TYPE = "type"
    BOUTIQUE_LIST = "list"

    def __init__(self, pipeline_name, folder_in, folder_out, subjects=None, options=None):

        # literal file name in niak
        self.pipeline_name = pipeline_name

        # The name should be Provided in the derived class
        self._grabber_options = []
        self._pipeline_options = []

        # if os.path.islink(folder_in):
        #     self.folder_in = os.readlink(folder_in)
        # else:
        self.folder_in = folder_in
        self.folder_out = folder_out
        self.octave_options = options

        if subjects is not None:
            self.subjects = unroll_numbers(subjects)
        else:
            self.subjects = None

        self.psom_gb_local_path = None

    def psom_gb_vars_local_setup(self):
        """
        This method is crucial to have psom/niak running properly on cbrain.
        :return:
        """
        self.psom_gb_local_path = "{0}/psom_gb_vars_local.m".format(LOCAL_CONFIG_PATH)
        shutil.copyfile(PSOM_GB_LOCAL, self.psom_gb_local_path)

    def run(self):
        print(" ".join(self.octave_cmd))
        p = None

        self.psom_gb_vars_local_setup()

        try:
            p = subprocess.Popen(self.octave_cmd)
            p.wait()
        except BaseException as e:
            if p and psutil_loaded:
                parent = psutil.Process(p.pid)
                try:
                    children = parent.children(recursive=True)
                except AttributeError:
                    children = parent.get_children(recursive=True)
                for child in children:
                    child.kill()
                parent.kill()
            raise e

    @property
    def octave_cmd(self):
        return ["/usr/bin/env", "octave", "--eval", "{0};{1}(files_in, opt)"
                           .format(";".join(self.octave_options), self.pipeline_name)]

    @property
    def octave_options(self):

        opt_list = ["opt.folder_out=\'{0}\'".format(self.folder_out)]

        opt_list += self.grabber_construction()

        if self._pipeline_options:
            opt_list += self._pipeline_options

        return opt_list

    @octave_options.setter
    def octave_options(self, options):

        if options is not None:
            # Sort options between grabber (the input file reader) and typecast
            # them with the help of the boutique descriptor
            with open("{0}/{1}.json".format(self.BOUTIQUE_PATH, self.__class__.__name__)) as fp:
                boutique_descriptor = json.load(fp)

            casting_dico = {elem.get(self.BOUTIQUE_CMD_LINE, "")
                            .replace("--opt", "opt").replace("-", "."): [elem.get(self.BOUTIQUE_TYPE),
                                                                         elem.get(self.BOUTIQUE_LIST)]
                            for elem in boutique_descriptor[self.BOUTIQUE_INPUTS]}

            for optk, optv in options.items():


                optv = self.BOUTIQUE_TYPE_CAST[casting_dico[optk][0]](optv)

                # if casting_dico[boutique_opt][1] is True:

                if optk.startswith("--opt_g"):
                    self._grabber_options.append("{0}={1}".format(optk, optv))
                else:
                    self._pipeline_options.append("{0}={1}".format(optk, optv))



    def grabber_construction(self):
        """
        This method needs to be overload to fill the file_in requirement of NIAK
        :return: A list that contains octave string that fill init the file_in variable
        """
        pass



class FmriPreprocess(BasePipeline):

    def __init__(self, *args, **kwargs):
        super(FmriPreprocess, self).__init__("niak_pipeline_fmri_preprocess", *args, **kwargs)

    def grabber_construction(self):
        """

        :return: A list that contains octave string that fill init the file_in variable

        """
        opt_list = []
        if os.path.isfile("{0}/{1}".format(os.getcwd(), self.folder_in)):
            in_full_path = "{0}/{1}".format(os.getcwd(), self.folder_in)
        else:
            in_full_path = "{0}".format(self.folder_in)
        list_in_dir = os.listdir(in_full_path)

        # TODO Control that with an option
        bids_description = None
        subject_input_list = None
        for f in list_in_dir:
            if f.endswith("dataset_description.json"):
                bid_path = "{0}/{1}".format(in_full_path, f)
                with open(bid_path) as fp:
                    bids_description = json.load(fp)

            elif f.endswith("_demographics.txt"):
                subject_input_list = f

        if subject_input_list:
            opt_list += ["list_subject=fcon_read_demog('{0}/{1}')".format(in_full_path, subject_input_list)]
            opt_list += ["opt_g.path_database='{0}/'".format(in_full_path)]
            opt_list += ["files_in=fcon_get_files(list_subject,opt_g)"]

        elif bids_description:
                if self.subjects is not None and len(self.subjects) >= 1:
                    opt_list += ["opt_gr.subject_list = {0}".format(self.subjects).replace('[', '{').replace(']', '}')]
                    opt_list += ["files_in=niak_grab_bids('{0}',opt_gr)".format(in_full_path)]
                else:
                    opt_list += ["files_in=niak_grab_bids('{0}')".format(in_full_path)]

                # opt_list += ["opt.slice_timing.flag_skip=true"]

        else:

            # Todo find a good strategy to load subject, to is make it general! --> BIDS
            # % Structural scan
            opt_list += ["files_in.subject1.anat=\'{0}/anat_subject1.mnc.gz\'".format(self.folder_in)]
            # % fMRI run 1
            opt_list += ["files_in.subject1.fmri.session1.motor=\'{0}/func_motor_subject1.mnc.gz\'".format(self.folder_in)]
            opt_list += ["files_in.subject2.anat=\'{0}/anat_subject2.mnc.gz\'".format(self.folder_in)]
            # % fMRI run 1
            opt_list += ["files_in.subject2.fmri.session1.motor=\'{0}/func_motor_subject2.mnc.gz\'".format(self.folder_in)]

        return opt_list


class BASC(BasePipeline):
    """
    Class to run basc. Only work with outputs from niak preprocessing,
    at least for now.
    """

    def __init__(self, *args, **kwargs):
        super(BASC, self).__init__("niak_pipeline_stability_rest", *args, **kwargs)

    def grabber_construction(self):
        """
        :return:
        """
        file_in = []


        file_in.append("opt_g.min_nb_vol = {0}")
        file_in.append("opt_g.type_files = 'rest'")
        if self.subjects is not None and len(self.subjects) >= 1:
            file_in.append("opt_g.include_subject = {0}".format(self.subjects).replace('[', '{').replace(']', '}'))
        file_in.append("files_in = niak_grab_fmri_preprocess('{0}',opt_g)".format(self.folder_in))


        return file_in



# Dictionary for supported class
SUPPORTED_PIPELINES = {"Niak_fmri_preprocess": FmriPreprocess,
                       "Niak_basc": BASC,
                       "Niak_stability_rest": BASC}


def load(pipeline_name, *args, **kwargs):

    if not pipeline_name or not pipeline_name in SUPPORTED_PIPELINES:
        m = 'Pipeline {0} is not in not supported\nMust be part of {1}'.format(pipeline_name, SUPPORTED_PIPELINES)
        raise IOError(m)

    pipe = SUPPORTED_PIPELINES[pipeline_name]

    return pipe(*args, **kwargs)



def unroll_numbers(numbers):
    import re

    entries = [a[0].split('-') for a in  re.findall("([0-9]+((-[0-9]+)+)?)", numbers)]

    unrolled = []
    for elem in entries:
        if len(elem) == 1:
            unrolled.append(int(elem[0]))
        elif len(elem) == 2:
            unrolled += [a for a in range(int(elem[0]), int(elem[1])+1)]
        elif len(elem) == 3:
            unrolled += [a for a in range(int(elem[0]), int(elem[1])+1, int(elem[2]) )]

    return sorted(list(set(unrolled)))

if __name__ == '__main__':
    # folder_in = "/home/poquirion/test/data_test_niak_mnc1"
    # folder_out = "/var/tmp"
    #
    # basc = BASC(folder_in=folder_in, folder_out=folder_out)
    #
    # print(basc.octave_cmd)

    print (unroll_numbers("1,3,4 15-20, 44, 18-27-2"))