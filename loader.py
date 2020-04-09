import math
import random
import multiprocessing
from time import time

import openslide
from utils import *


class BasicLoader:
    def __init__(self, slide_folder, save_folder,
                 target_size=400, ds_rate=0, n_procs=4, overlap=False, default_ol_sz=300,
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_thresh=10):
        self.slide_folder = slide_folder
        self.save_folder = save_folder
        self.ds_rate = ds_rate
        self.patch_size = target_size
        self.n_procs = n_procs if 0 <= n_procs < 10 else 3
        self.overlap = overlap
        self.default_ol_sz = default_ol_sz
        self.rm_blank = rm_blank
        self.blank_range = blank_range
        self.rm_black = rm_black
        self.black_thresh = black_thresh

        self.checks_io_folders()
        self.slide_names_list = get_slide_names(slide_folder)
        print(f' \nWSI Extractor')
        print(f'{"-" * 20} \nFind {len(self.slide_names_list)} slides. \n{"-" * 20}')

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
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_thresh=10):
        super(TileSaving, self).__init__(
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
            black_thresh=black_thresh
        )

        # The following variables will change with loop
        self.restore_self_vars()

    def restore_self_vars(self):
        subclass_var_dict = ('sp', 'name', 'rows', 'columns',
                             'slide_save_path', 'ds_scale', 'time_flag')
        for var in subclass_var_dict:
            setattr(self, var, None)

    def _slide_info(self):
        time_flag = time()
        print(f'\nLoaded slide: {self.name} ... ')
        slide_width, slide_height = self.sp.level_dimensions[self.ds_rate]
        rows, columns = self.get_rows_columns(slide_width, slide_height)
        ds_scale = round(self.sp.level_downsamples[self.ds_rate])
        print(f'  width: {slide_width}, height: {slide_height}, \n'
              f'  rows: {rows}, columns: {columns}, \n'
              f'  ds scale: {ds_scale}, patch size: {self.patch_size}')
        print(f'  Creating save folder ... ', end='  ')
        slide_save_path = os.path.join(
            self.save_folder, f'{os.path.splitext(self.name)[0]}_{rows}_{columns}_x{ds_scale}_sz{self.patch_size}')
        if type(self) is TileSaving:
            check_path_valid(slide_save_path, create=True)
        print('done')
        return rows, columns, slide_save_path, ds_scale, time_flag

    def _process_target(self, start_n, cols_per_process):
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
                patch_name = f'{os.path.splitext(self.name)[0]}_{batch_id}_{c}.jpg'
                if self.rm_black and self.rm_blank:
                    check_valid_save_patch(patch, os.path.join(batch_save_path, patch_name),
                                           self.black_thresh, self.blank_range)
                else:
                    save_patch(patch, os.path.join(batch_save_path, patch_name))
        print(f'  Finished {start_n} - {end_ncol} columns, used time: {time() - self.time_flag :.2f} s.')

    def tiling(self):
        for sp, name in self.slide_pointer_generator():
            self.sp, self.name = sp, name
            self.rows, self.columns, self.slide_save_path, self.ds_scale, self.time_flag = self._slide_info()

            cols_per_process = math.ceil(self.rows / self.n_procs)
            process_start_ncol_list = [n_col for n_col in range(self.rows) if n_col % cols_per_process == 0]
            if len(process_start_ncol_list) != self.n_procs:
                assert len(process_start_ncol_list) < self.n_procs
                print(f'  self-Adaptive modification of n_procs, '
                      f'default: {self.n_procs} process, used: {len(process_start_ncol_list)} process, '
                      f'max {cols_per_process} columns per process.')
                self.n_procs = len(process_start_ncol_list)
            else:
                print('  Using default settings, used %d process, %d columns per process.'
                      % (self.n_procs, cols_per_process))
            assert len(process_start_ncol_list) == self.n_procs

            p = [None] * self.n_procs
            for proc in range(self.n_procs):
                p[proc] = multiprocessing.Process(
                    target=self._process_target, args=(process_start_ncol_list[proc], cols_per_process, ))
                p[proc].start()
            for proc in range(self.n_procs):
                p[proc].join()

            self.restore_self_vars()


class TestDataGenerator(TileSaving):
    def __init__(self, slide_folder, target_size=400, ds_rate=0, n_procs=4, overlap=False, default_ol_sz=300,
                 rm_blank=True, blank_range=(200, 225), rm_black=True, black_thresh=10):
        super(TestDataGenerator, self).__init__(
            slide_folder=slide_folder,
            save_folder=slide_folder,  # save_folder must be a valid path though we not use it here
            target_size=target_size,
            ds_rate=ds_rate,
            n_procs=n_procs,
            overlap=overlap,
            default_ol_sz=default_ol_sz,
            rm_blank=rm_blank,
            rm_black=rm_black,
            blank_range=blank_range,
            black_thresh=black_thresh
        )

    def _process_target(self, cols_list, cols_per_process=0):
        for r in cols_list:
            for c in range(self.columns):
                target_size = self.default_ol_sz if self.overlap else self.patch_size
                start_rc = [target_size * r * self.ds_scale, target_size * c * self.ds_scale]

                patch = self.get_patch(self.sp, start_rc)
                if self.rm_black and self.rm_blank:
                    if not check_patch_blank(patch, self.blank_range):
                        yield -2, r, c
                    elif not check_patch_black(patch, self.black_thresh):
                        yield -1, r, c
                    else:
                        yield patch, r, c
                else:
                    yield patch, r, c

    def get_patch_generator(self, mode, seed=None):
        if not (mode == 'random' or mode == 'sequence'):
            raise TypeError('mode: [random|sequence]')

        for idx, (sp, name) in enumerate(self.slide_pointer_generator()):
            self.sp, self.name = sp, name
            self.rows, self.columns, self.slide_save_path, self.ds_scale, self.time_flag = self._slide_info()
            perm = [i for i in range(self.rows)]
            if mode == 'random':
                if seed:
                    random.seed = seed
                random.shuffle(perm)
            yield self._process_target(perm), idx


if __name__ == '__main__':
    slide_folder = os.path.join(os.curdir, 'data', 'slide')
    save_folder = os.path.join(os.curdir, 'data', 'patch')

    # # Testing tiling
    TileSaving(slide_folder, save_folder, n_procs=4, target_size=512, ds_rate=0, black_thresh=50).tiling()

    # Testing generator
    loader_sequence = TestDataGenerator(slide_folder).get_patch_generator(mode='sequence')
    for patch_gen_seq, idx_seq in loader_sequence:
        i, j, k = [], [], []
        for patch_seq, c_seq, r_seq in patch_gen_seq:
            if patch_seq == -1:
                # patch is black
                i.append([r_seq, c_seq])
            elif patch_seq == -2:
                # patch is blank
                j.append([r_seq, c_seq])
            else:
                k.append([r_seq, c_seq])
        break

    loader_randomly = TestDataGenerator(slide_folder).get_patch_generator(mode='random')
    for patch_gen_rad, idx in loader_randomly:
        p, q, y = [], [], []
        for patch_rad, c_rad, r_rad in patch_gen_rad:
            if patch_rad == -1:
                # patch is black
                p.append([r_rad, c_rad])
            elif patch_rad == -2:
                # patch is blank
                q.append([r_rad, c_rad])
            else:
                y.append([r_rad, c_rad])
        break

    a = 10