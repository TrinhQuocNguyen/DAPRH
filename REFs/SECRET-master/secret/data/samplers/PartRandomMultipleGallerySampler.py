from __future__ import absolute_import
from collections import defaultdict
import math

import numpy as np
import copy
import random
import torch
from torch.utils.data.sampler import (
    Sampler, SequentialSampler, RandomSampler, SubsetRandomSampler,
    WeightedRandomSampler)

def No_index(a, b):
    assert isinstance(a, list)
    return [i for i, j in enumerate(a) if j != b]

class PartRandomMultipleGallerySampler(Sampler):
    def __init__(self, data_source, num_instances=4, batch_size=4):
        self.data_source = data_source
        self.index_pid = defaultdict(int)
        self.pid_cam = defaultdict(list)
        self.pid_index = defaultdict(list)
        self.num_instances = num_instances
        self.batch_size = batch_size

        for index, (_, pid, cam) in enumerate(data_source):
            pid_ = pid[0]
            self.index_pid[index] = pid_
            self.pid_cam[pid_].append(cam)
            self.pid_index[pid_].append(index)

        self.pids = list(self.pid_index.keys())
        self.num_samples = len(self.pids)

    def __len__(self):
        len = self.num_samples * self.num_instances
        return len if len >= self.batch_size else self.batch_size

    def __iter__(self):
        ret = []
        while len(ret) < self.__len__():
            indices = torch.randperm(len(self.pids)).tolist()
            for kid in indices:
                i = random.choice(self.pid_index[self.pids[kid]])

                _, i_pid, i_cam = self.data_source[i]

                ret.append(i)

                pid_i = self.index_pid[i]
                cams = self.pid_cam[pid_i]
                index = self.pid_index[pid_i]
                select_cams = No_index(cams, i_cam)

                if select_cams:

                    if len(select_cams) >= self.num_instances:
                        cam_indexes = np.random.choice(select_cams, size=self.num_instances-1, replace=False)
                    else:
                        cam_indexes = np.random.choice(select_cams, size=self.num_instances-1, replace=True)

                    for kk in cam_indexes:
                        ret.append(index[kk])

                else:
                    select_indexes = No_index(index, i)
                    if (not select_indexes): continue
                    if len(select_indexes) >= self.num_instances:
                        ind_indexes = np.random.choice(select_indexes, size=self.num_instances-1, replace=False)
                    else:
                        ind_indexes = np.random.choice(select_indexes, size=self.num_instances-1, replace=True)

                    for kk in ind_indexes:
                        ret.append(index[kk])


        return iter(ret)
