import os
os.environ["CUDA_DEVICE_ORDER"]="PCI_BUS_ID"   
import sys
import argparse

import timeit
start_time = timeit.default_timer()

parser = argparse.ArgumentParser()
parser.add_argument('-mode', type=str, help='rgb or flow')
parser.add_argument('-load_model', type=str)
parser.add_argument('-root', type=str)
parser.add_argument('-gpu', type=str)
parser.add_argument('-save_dir', type=str)

args = parser.parse_args()
os.environ["CUDA_VISIBLE_DEVICES"]=args.gpu

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.optim import lr_scheduler
from torch.autograd import Variable

import torchvision
from torchvision import datasets, transforms
import videotransforms


import numpy as np

from pytorch_i3d import InceptionI3d

from charades_dataset_full import Charades as Dataset


def run(max_steps=64e3, mode='rgb', root='/ssd2/charades/Charades_v1_rgb', split='./charades/charades.json', batch_size=1, load_model='', save_dir=''):
    # setup dataset
    test_transforms = transforms.Compose([videotransforms.CenterCrop(224)])

    dataset = Dataset(split, 'training', root, mode, test_transforms, num=-1, save_dir=save_dir)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=8, pin_memory=True)
    print('training data read')
    
    val_dataset = Dataset(split, 'testing', root, mode, test_transforms, num=-1, save_dir=save_dir)
    val_dataloader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=True, num_workers=8, pin_memory=True)    
    print('validation data read')
    
    dataloaders = {'train': dataloader, 'val': val_dataloader}
    dataloaders = {'val': val_dataloader, 'train': dataloader}
    datasets = {'train': dataset, 'val': val_dataset}

    
    # setup the model
    if mode == 'flow':
        i3d = InceptionI3d(400, in_channels=2)
    else:
        i3d = InceptionI3d(400, in_channels=3)
    i3d.replace_logits(157)
    i3d.load_state_dict(torch.load(load_model))
    i3d.cuda()
    print('model set')

    for phase in ['train', 'val']:
        print('starting phase', phase)
        i3d.eval()  #i3d.train(False)  # Set model to evaluate mode
        print('time in line 68=', str(timeit.default_timer() - start_time))
                
        tot_loss = 0.0
        tot_loc_loss = 0.0
        tot_cls_loss = 0.0
                    
        # Iterate over data.
        for data in dataloaders[phase]:
            # get the inputs
            inputs, labels, name = data
            if os.path.exists(os.path.join(save_dir, name[0]+'.npy')):
                print('features of ', name, 'already exist... omitting')
                continue

            b,c,t,h,w = inputs.shape
            max_len = 800
            print('time in line 84=', str(timeit.default_timer() - start_time))
            if t > max_len:
                features = []
                for start in range(1, t-56, max_len):
                    end = min(t-1, start+max_len+56)
                    start = max(1, start-48)
                    ip = Variable(torch.from_numpy(inputs.numpy()[:,:,start:end]).cuda(), volatile=True)
                    features.append(i3d.extract_features(ip).squeeze(0).permute(1,2,3,0).data.cpu().numpy())
                print('saving', name[0])
                np.save(os.path.join(save_dir, name[0]), np.concatenate(features, axis=0))                
            else:
                # wrap them in Variable
                inputs = Variable(inputs.cuda(), volatile=True)
                features = i3d.extract_features(inputs)
                print('saving', name[0])
                np.save(os.path.join(save_dir, name[0]), features.squeeze(0).permute(1,2,3,0).data.cpu().numpy())


if __name__ == '__main__':
    # need to add argparse
    run(mode=args.mode, root=args.root, load_model=args.load_model, save_dir=args.save_dir)
