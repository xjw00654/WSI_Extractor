import os
import openslide
import multiprocessing
import numpy as np
from time import time
from math import ceil
from PIL import Image


class SlideLoader:
    def __init__(self, dataPath, savePath, downsample,
                 endsFormat='ndpi', patchsize=400, nProcs=4,
                 overlap=1, default_overlap_size=300,
                 removeBlankPatch=0, blankRange=(200, 225),
                 removeBlackPatch=0, blackLevel=10):
        self.slidePath = dataPath
        self.savePath = savePath
        self.savePath_slide = ''
        self.slideName = ''
        self.downsample = downsample
        self.patchsize = patchsize
        self.nProcs = nProcs
        self.margin = overlap
        self.marginsize = default_overlap_size
        self.removeBlank = removeBlankPatch
        self.balnkRange = blankRange
        self.removeBlack = removeBlackPatch
        self.blackLevel = blackLevel
        self.downsample_scale = -1
        self.slidewidth = -1
        self.slideheight = -1
        self.rows = -1
        self.columns = -1
        self.marker = endsFormat
        self.tic = -1
        self.slideList = []
        self.slidePointer = None
        for root, _, fnames in os.walk(self.slidePath):
            for fname in fnames:
                if fname.endswith(self.marker):
                    self.slideList.append(os.path.join(root, fname))

    def getSlide(self, index):
        self.tic = self.time_()
        self.slideName = self.slideList[index].split('/')[-1][:-len(self.marker)-1]
        self.slidePointer = openslide.OpenSlide(self.slideList[index])
        [self.slidewidth, self.slideheight] = self.slidePointer.level_dimensions[self.downsample]

        # margin version
        if self.margin != 0:
            self.rows = (self.slidewidth // self.marginsize)
            self.columns = (self.slideheight // self.marginsize)
        else:
            self.rows = (self.slidewidth // self.patchsize)
            self.columns = (self.slideheight // self.patchsize)
        self.downsample_scale = int(self.slidePointer.level_downsamples[self.downsample])
        self.savePath_slide = os.path.join(
            self.savePath, self.slideName + '_' + str(self.rows) + '_' + str(self.columns))
        if not os.path.exists(self.savePath_slide):
            os.mkdir(self.savePath_slide)
        print('Loaded image: %s' % self.slideList[index])
        print('Width: %d, Height: %d' % (self.slidewidth, self.slideheight))

    def time_(self, tic=0.0):
        if tic == 0.0:
            return time()
        else:
            return time() - tic

    def getPatch(self, startIndex):
        # function for getting patch
        sz = (self.patchsize, self.patchsize)
        patch = self.slidePointer.read_region(startIndex, self.downsample, sz)
        return patch

    def savePatch(self, patch, path):
        # function for saving patch
        if self.removeBlank == 1 and self.checkBlank(patch) == -1 or self.removeBlack == 1 and self.checkBlack(patch) == -1:
            return 0
        else:
            patch.convert("RGB").save(path)

    def checkBlack(self, patch):
        patch = np.array(patch.convert("RGB"))
        m = patch.mean()
        if m <= self.blackLevel:
            return -1
        else:
            return Image.fromarray(patch)

    def checkBlank(self, patch):
        patch = np.array(patch.convert("RGB"))
        m = patch.mean()
        if self.balnkRange[0] <= m <= self.balnkRange[1]:
            return -1
        else:
            return Image.fromarray(patch)

    def checkLayers(self):
        for one in self.slideList:
            if one.level_count < 3:
                raise ValueError('Slide only contain 1 or 2 layer(s).')

    def threadTarget(self, startIndex, perThread):
        threadT = self.time_()
        for i in range(startIndex, min(startIndex + int(perThread), self.rows)):
            for j in range(self.columns):
                Num = i * self.columns + j
                if Num % self.columns == 0:
                    # print('%s, batch %d/%d' %
                    #       (multiprocessing.current_process().name, i, perThread))
                    savepath_batch = os.path.join(
                        self.savePath_slide, 'batch' + str(Num // self.columns))
                    if not os.path.exists(savepath_batch):
                        os.mkdir(savepath_batch)

                # margin version
                if self.margin:
                    startIndex = [self.marginsize * i * self.downsample_scale,
                                  self.marginsize * j * self.downsample_scale]
                else:
                    startIndex = [self.patchsize * i * self.downsample_scale,
                                  self.patchsize * j * self.downsample_scale]

                patch = self.getPatch(startIndex)
                imgName = self.slideName + '_' + str(i) + '_' + str(j) + '.jpg'
                self.savePatch(patch, os.path.join(savepath_batch, imgName))
        print('time: %.2f' % self.time_(threadT))

    def threadProcessing(self):
        # seperate work
        perThread = ceil(self.rows / self.nProcs)
        startIndex = [one for one in range(self.rows) if one % perThread == 0]
        if len(startIndex) != self.nProcs:
            assert len(startIndex) < self.nProcs
            print('Self-Adaptive modification of nProcs, '
                  'default: %d process, used: %d process, '
                  '%d columns per process.'
                  % (self.nProcs, len(startIndex), perThread))
            self.nProcs = len(startIndex)
        else:
            print('Use default settings, used %d process, %d columns per process.'
                  % (self.nProcs, perThread))
        assert len(startIndex) == self.nProcs

        p = [None] * self.nProcs
        for Proc in range(self.nProcs):
            p[Proc] = multiprocessing.Process(
                target=self.threadTarget, args=(startIndex[Proc], perThread, ))
            p[Proc].start()
        for Proc in range(self.nProcs):
            p[Proc].join()
        print('Process ending.')

    def mainProcess(self, skip=False, nskip=0):
        for index, oneslide in enumerate(self.slideList):
            if skip:
                if index < nskip:
                    continue
            self.getSlide(index)
            self.threadProcessing()


def check_python_version():
    import sys
    if not sys.version_info > (3, ):
        raise EnvironmentError(
            'Please use Python3 or uncomment __future__ import.')


def main():
    check_python_version()
    slidepath = '/home/xjw/Projects/IHC_extraction/data/slide/'
    outPath = '/home/xjw/Projects/IHC_extraction/data/patch/'

    # 0: 40x, 1: 20x, 2: 10x, ...
    # loader = SlideLoader(slidepath, outPath,
    #                      downsample=2, patchsize=400,
    #                      nProcs=8, overlap=1, default_overlap_size=300,
    #                      removeBlankPatch=0)
    loader = SlideLoader(slidepath, outPath, downsample=1, endsFormat='ndpi',
                         patchsize=512, nProcs=4, overlap=0, default_overlap_size=300,
                         removeBlankPatch=1, blankRange=[190, 210])
    loader.mainProcess(skip=False, nskip=17)


if __name__ == "__main__":
    main()
