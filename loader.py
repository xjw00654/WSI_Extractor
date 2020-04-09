import os
import math
import random
import multiprocessing
from time import time

import openslide
from .utils import *


class BasicLoader:
    def __init__(self, slide_folder, save_folder,
                 target_size=400, ds_rate=0, n_procs=4, overlap=False, default_ol_sz=300,
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_range=10):
        self.slide_folder = slide_folder
        self.save_folder = save_folder
        self.ds_rate = ds_rate
        self.patch_size = target_size
        self.nProcs = n_procs if 0 <= n_procs < 10 else 3
        self.overlap = overlap
        self.default_ol_sz = default_ol_sz
        self.rm_blank = rm_blank
        self.blank_range = blank_range
        self.rm_black = rm_black
        self.black_range = black_range

        self.checks_io_folders()
        self.slide_names_list = get_slide_names(slide_folder)
        print(f' {"-" * 20} \n Find {len(self.slide_names_list)} slides. \n {"-" * 20}')

    def checks_io_folders(self):
        if not check_path_valid(self.slide_folder, create=False):
            raise FileNotFoundError('Folder does not exists.')
        if not check_path_valid(self.save_folder, create=True):
            print(f'  Can not find save folder, will create {self.save_folder}.')

    def get_rows_columns(self, width, height):
        if width * height <= 0:
            raise ValueError('Got wrong wdith and height value of slide.')
        if self.overlap:
            rows, columns = width // self.default_ol_sz, height // self.default_ol_sz
        else:
            rows, columns = width // self.default_ol_sz, height // self.default_ol_sz
        return rows, columns

    def slide_pointer_generator(self):
        for slide_path in self.slide_names_list:
            yield openslide.OpenSlide(slide_path), os.path.basename(slide_path)

    def get_patch(self, pointer, start_rc):
        patch = pointer.read_region(start_rc, self.ds_rate, (self.patch_size, self.patch_size))
        return patch


class TileSaving(BasicLoader):
    def __init__(self, slide_folder, save_folder,
                 target_size=400, ds_rate=0, n_procs=4, overlap=False, default_ol_sz=300,
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_range=10):
        super(BasicLoader, self).__init__(
            slide_folder=slide_folder,
            save_folder=save_folder,
            target_size=target_size,
            ds_rate=ds_rate,
            n_procs=n_procs,
            overlap=overlap,
            default_ol_sz=default_ol_sz,
            rm_blank=rm_blank,
            rm_black=rm_black,
            blank_range=blank_range,
            black_range=black_range,
        )
        # The following private variables will change with loop
        self.sp = None  # slide pointer
        self.name = None  # slide name
        self.rows = None
        self.columns = None
        self.slide_save_path = None
        self.ds_scale = None
        self.time_flag = None

    def restore_self_vars(self):
        for var in self.__dict__.keys():
            setattr(self, var, None)

    def slide_info(self):
        time_flag = time()
        print(f'Loaded slide: {self.name} ... ')
        slide_width, slide_height = self.sp.level_dimensions[self.ds_rate]
        rows, columns = self.get_rows_columns(slide_width, slide_height)
        ds_scale = round(self.sp.level_downsamples[self.ds_rate])
        print(f'  width: {slide_width}, height: {slide_height}, '
              f'  rows: {rows}, columns: {columns}, \n'
              f'  downsample scale: {ds_scale}')
        print(f'  creating save folder ... ', end='  ')
        slide_save_path = os.path.join(self.save_folder, self.name)
        os.mkdir(slide_save_path)
        print('done')
        return rows, columns, slide_save_path, ds_scale, time_flag

    def process_target(self, start_n, cols_per_process, save=True):
        end_ncol = min(start_n + int(cols_per_process), self.rows)
        for r in range(start_n, end_ncol):
            for c in range(self.columns):
                col_loc = r * self.columns + c
                batch_id = col_loc // self.columns

                batch_save_path = os.path.join(self.slide_save_path, f'batch{batch_id}')
                check_path_valid(batch_save_path, create=True)

                target_size = self.default_ol_sz if self.overlap else self.patch_size
                start_rc = [target_size * r * self.ds_scale, target_size * c * self.ds_scale]

                patch = self.get_patch(self.sp, start_rc)
                if save:
                    patch_name = f'{os.path.splitext(self.name)[0]}_{batch_id}_{c}.jpg'
                    if self.rm_black and self.rm_blank:
                        check_valid_save_patch(patch, os.path.join(batch_save_path, patch_name),
                                               self.black_range, self.blank_range)
                    else:
                        save_patch(patch, os.path.join(batch_save_path, patch_name))
                else:
                    yield patch
        print(f'  finished {start_n} - {end_ncol} columns, used time: {time() - self.time_flag} s.')

    def tiling(self):
        for sp, name in self.slide_pointer_generator():
            self.sp, self.name = sp, name
            self.rows, self.columns, self.slide_save_path, self.ds_scale, self.time_flag = self.slide_info()

            cols_per_process = math.ceil(self.rows / self.nProcs)
            process_start_ncol_list = [n_col for n_col in range(self.rows) if n_col % cols_per_process == 0]
            if len(process_start_ncol_list) != self.nProcs:
                assert len(process_start_ncol_list) < self.nProcs
                print(f'  self-Adaptive modification of nProcs, '
                      f'default: {self.nProcs} process, used: {len(process_start_ncol_list)} process, '
                      f'max {cols_per_process} columns per process.')
                self.nProcs = len(process_start_ncol_list)
            else:
                print('Use default settings, used %d process, %d columns per process.'
                      % (self.nProcs, cols_per_process))
            assert len(process_start_ncol_list) == self.nProcs

            process_pointer = [None] * self.nProcs
            for proc in range(self.nProcs):
                process_pointer[proc] = multiprocessing.Process(
                    target=self.process_target, args=(process_start_ncol_list[proc], cols_per_process,))
                process_pointer[proc].start()
            for proc in range(self.nProcs):
                process_pointer[proc].join()

            self.restore_self_vars()


class SequenceGenerator(TileSaving):
    def __init__(self, slide_folder, target_size=400, ds_rate=0, n_procs=4, overlap=False, default_ol_sz=300,
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_range=10):
        super(TileSaving, self).__init__(
            slide_folder=slide_folder,
            save_folder=None,
            target_size=target_size,
            ds_rate=ds_rate,
            n_procs=n_procs,
            overlap=overlap,
            default_ol_sz=default_ol_sz,
            rm_blank=rm_blank,
            rm_black=rm_black,
            blank_range=blank_range,
            black_range=black_range
        )

    def get_item_slide_generator(self, item):


class TestDataGenerator(TileSaving):
    def __init__(self, slide_folder, target_size=400, ds_rate=0, n_procs=4, overlap=False, default_ol_sz=300,
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_range=10):
        super(TileSaving, self).__init__(
            slide_folder=slide_folder,
            save_folder=None,
            target_size=target_size,
            ds_rate=ds_rate,
            n_procs=n_procs,
            overlap=overlap,
            default_ol_sz=default_ol_sz,
            rm_blank=rm_blank,
            rm_black=rm_black,
            blank_range=blank_range,
            black_range=black_range
        )

    def get_patch_generator_in_sequence(self):
        """
        This function will generate patch generator by slides in sequence(column)
        :return: patch generator
        """

        for idx, (sp, name) in enumerate(self.slide_pointer_generator()):
            self.sp, self.name = sp, name
            self.rows, self.columns, self.slide_save_path, self.ds_scale, self.time_flag = self.slide_info()
            yield self.process_target(0, self.rows, save=False)

    def get_patch_generator_randomly(self, seed=None):
        """
        This function will generate patch generation randomly(column)
        :param seed: random seeds
        :return: patches of random column
        """

        for idx, (sp, name) in enumerate(self.slide_pointer_generator()):
            self.sp, self.name = sp, name
            self.rows, self.columns, self.slide_save_path, self.ds_scale, self.time_flag = self.slide_info()

            randomperm = sorted((i for i in range(self.rows)))
            for c in randomperm:
                yield self.process_target(c, 1, save=False)
