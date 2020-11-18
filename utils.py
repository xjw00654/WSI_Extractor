import os
import sys
import numpy as np


def get_slide_names(dir_name):
    slide_name_list = []
    slide_format = ['.svs', '.ndpi', '.mrxs', '.tif', '.tiff']
    for root, _, f_names in os.walk(dir_name):
        for f_name in f_names:
            if os.path.splitext(f_name)[1].lower() in slide_format:
                slide_name_list.append(os.path.join(root, f_name))
    if len(slide_name_list) == 0:
        raise FileNotFoundError(f'Could not find slide(s) in {dir_name}, '
                                f'current support ext: {slide_format}')
    else:
        return slide_name_list


def get_xml_list(dir_name: (str, list, tuple)) -> list:
    if type(dir_name) == str:
        return [os.path.join(dir_name, elem)
                for elem in os.listdir(dir_name)
                if elem.lower().endswith('.xml')]
    elif type(dir_name) in (list, tuple):
        data_list = []
        while dir_name:
            data_list += get_xml_list(dir_name.pop())
        return data_list
    else:
        raise TypeError('Unsupported [dir_name] when calling \'get_xml_list\'')


def check_xml_slide_align(slide_list: list, xml_list: list):
    slide_list = set([os.path.splitext(os.path.basename(elem))[0] for elem in slide_list])
    xml_list = set([os.path.splitext(os.path.basename(elem))[0] for elem in xml_list])

    return xml_list <= slide_list


def check_path_valid(path, create=False):
    if os.path.exists(path):
        return True
    else:
        if create:
            os.makedirs(path)
        return False


def check_patch_black(patch, black_thresh):
    patch = np.array(patch).mean()
    if patch <= black_thresh:
        return False
    else:
        return True


def check_patch_blank(patch, blank_range):
    patch = np.array(patch).mean()
    if blank_range[0] <= patch <= blank_range[1]:
        return False
    else:
        return True


def check_patch_valid(patch, black_thresh, blank_range):
    if not type(black_thresh) is int:
        raise ValueError(f'\'black_thresh\' must have one elements, current {black_thresh}')
    elif len(blank_range) != 2:
        raise ValueError(f'\'blank_range\' must have 2 elements, current {blank_range}')
    elif not 0 <= blank_range[0] <= 255 and not 0 <= blank_range[0] <= 255:
        raise ValueError(f'\'blank_range\' must be 2 \'uint8\' format number.')
    elif not 0 <= black_thresh <= 255:
        raise ValueError(f'\'black_thresh\' must be a \'uint8\' format number.')

    patch = patch.convert("RGB")
    if not check_patch_black(patch, black_thresh):
        return -1
    elif not check_patch_blank(patch, blank_range):
        return -2
    else:
        return True


def check_valid_save_patch(patch, save_path, black_thresh, blank_range, dummy_print=True):
    flag = check_patch_valid(patch, black_thresh, blank_range)
    if flag == -1:
        if not dummy_print:
            print(f'  {os.path.basename(save_path)} is blaCk, will pass.')
    elif flag == -2:
        if not dummy_print:
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
