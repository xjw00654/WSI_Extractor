import os
import sys
import numpy as np


def get_slide_names(dir_name):
    slide_name_list = []
    slide_format = ['.svs', '.ndpi', '.mrxs']
    for root, _, f_names in os.walk(dir_name):
        for f_name in f_names:
            if os.path.splitext(f_name)[1] in slide_format:
                slide_name_list.append(os.path.join(root, f_name))
    if len(slide_name_list) == 0:
        raise FileNotFoundError(f'Could not find slide(s) in {dir_name}, current support ext: {slide_format}')
    else:
        return slide_name_list


def check_path_valid(path, create=False):
    if os.path.exists(path):
        return True
    else:
        if create:
            os.makedirs(path)
        return False


def check_patch_black(patch_mean, black_range):
    if patch_mean <= black_range:
        return False
    else:
        return True


def check_patch_blank(patch_mean, blank_range):
    if blank_range[0] <= patch_mean <= blank_range[1]:
        return False
    else:
        return True


def check_patch_valid(patch, black_range, blank_range):
    if len(black_range) != 2:
        raise ValueError(f'\'black_range\' must have 2 elements, current {black_range}')
    elif len(blank_range) != 1:
        raise ValueError(f'\'blank_range\' must have one elements, current {blank_range}')
    elif not 0 <= black_range[0] <= 255 and not 0 <= black_range[0] <= 255:
        raise ValueError(f'\'black_range\' must be 2 \'uint8\' format number.')
    elif not 0 <= blank_range <= 255:
        raise ValueError(f'\'blank_range\' must be a \'uint8\' format number.')

    patch_array = np.array(patch.convert("RGB"))
    patch_mean = patch_array.mean()
    if not check_patch_black(patch_mean, black_range):
        return -1
    elif not check_patch_blank(patch_mean, blank_range):
        return -2
    else:
        return True


def check_valid_save_patch(patch, save_path, black_range, blank_range, dummy_print=True):
    flag = check_patch_valid(patch, black_range, blank_range)
    if flag == -1:
        if dummy_print:
            print(f'  {os.path.basename(save_path)} is blaCk, will pass.')
    elif flag == -2:
        if dummy_print:
            print(f'  {os.path.basename(save_path)} is blaNk, will pass.')
    elif flag:
        patch.convert("RGB").save(save_path)
    else:
        Warning('Unknown return value, we are not sure the result(s) is correct.')


def save_patch(patch, save_path):
    patch.convert("RGB").save(save_path)


def check_python_version():
    if not sys.version_info >= (3, 7):
        raise EnvironmentError('Please use Python version over 3.7 to support f-string.')