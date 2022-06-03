# encoding: utf-8
"""
@author:  l1aoxingyu
@contact: sherlockliao01@gmail.com
"""

import os
int_classes= int
import torch
import collections.abc as container_abcs
from torch._six import string_classes
from torch.utils.data import DataLoader

from fastreid.utils import comm
from . import samplers
from .common import CommDataset
from .datasets import DATASET_REGISTRY
from .transforms import build_transforms
import pdb

_root = os.getenv("FASTREID_DATASETS", "datasets")


def build_reid_train_loader(cfg, mapper=None, **kwargs):
    cfg = cfg.clone()

    train_items = list()
    train_items1 = list()
    for d in cfg.DATASETS.NAMES:
        dataset = DATASET_REGISTRY.get(d)(root=_root, combineall=cfg.DATASETS.COMBINEALL, **kwargs)
        if d != 'YouTube':
            if comm.is_main_process():
                dataset.show_train()
            train_items.extend(dataset.train)
        else:
            train_items1.extend(dataset.train)
            #dataset.show_train()
    if not len(train_items1) > 0: #just train with labelled data and not contain YoutubeDS
        train_items1 = train_items.copy()[:100]
        
    if mapper is not None:
        transforms = mapper
    else:
        transforms = build_transforms(cfg, is_train=True)

    train_set = CommDataset(train_items, transforms, relabel=True)
    train_set1 = CommDataset(train_items1, transforms, relabel=True)

    num_workers = cfg.DATALOADER.NUM_WORKERS
    num_instance = cfg.DATALOADER.NUM_INSTANCE
    mini_batch_size = cfg.SOLVER.IMS_PER_BATCH // comm.get_world_size()

    if cfg.DATALOADER.PK_SAMPLER:
        if cfg.DATALOADER.NAIVE_WAY:
            data_sampler = samplers.NaiveIdentitySampler(train_set.img_items, mini_batch_size, num_instance)
        else:
            data_sampler = samplers.BalancedIdentitySampler(train_set.img_items, mini_batch_size, num_instance)
    else:
        data_sampler = samplers.TrainingSampler(len(train_set))

    data_sampler1 = samplers.TrainingSampler(len(train_set1))
    batch_sampler = torch.utils.data.sampler.BatchSampler(data_sampler, mini_batch_size, True)
    batch_sampler1 = torch.utils.data.sampler.BatchSampler(data_sampler1, 48, True)
    train_loader = torch.utils.data.DataLoader(
        train_set,
        num_workers=num_workers,
        batch_sampler=batch_sampler,
        collate_fn=fast_batch_collator,
        pin_memory=True,
    )
    train_loader1 = torch.utils.data.DataLoader(
        train_set1,
        num_workers=num_workers,
        batch_sampler=batch_sampler1,
        collate_fn=fast_batch_collator,
        pin_memory=True,
    )
    return train_loader, train_loader1


def build_reid_test_loader(cfg, dataset_name, mapper=None, **kwargs):
    cfg = cfg.clone()

    dataset = DATASET_REGISTRY.get(dataset_name)(root=_root, **kwargs)
    if comm.is_main_process():
        dataset.show_test()
    test_items = dataset.query + dataset.gallery

    if mapper is not None:
        transforms = mapper
    else:
        transforms = build_transforms(cfg, is_train=False)

    test_set = CommDataset(test_items, transforms, relabel=False)

    mini_batch_size = cfg.TEST.IMS_PER_BATCH // comm.get_world_size()
    data_sampler = samplers.InferenceSampler(len(test_set))
    batch_sampler = torch.utils.data.BatchSampler(data_sampler, mini_batch_size, False)
    test_loader = DataLoader(
        test_set,
        batch_sampler=batch_sampler,
        num_workers=4,  # save some memory
        collate_fn=fast_batch_collator,
        pin_memory=True,
    )
    return test_loader, len(dataset.query)


def trivial_batch_collator(batch):
    """
    A batch collator that does nothing.
    """
    return batch


def fast_batch_collator(batched_inputs):
    """
    A simple batch collator for most common reid tasks
    """
    elem = batched_inputs[0]
    if isinstance(elem, torch.Tensor):
        out = torch.zeros((len(batched_inputs), *elem.size()), dtype=elem.dtype)
        for i, tensor in enumerate(batched_inputs):
            out[i] += tensor
        return out

    elif isinstance(elem, container_abcs.Mapping):
        return {key: fast_batch_collator([d[key] for d in batched_inputs]) for key in elem}

    elif isinstance(elem, float):
        return torch.tensor(batched_inputs, dtype=torch.float64)
    elif isinstance(elem, int_classes):
        return torch.tensor(batched_inputs)
    elif isinstance(elem, string_classes):
        return batched_inputs
