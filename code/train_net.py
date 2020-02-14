#!/usr/bin/env python3
from __future__ import print_function

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim import lr_scheduler
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt
import time
import os
import copy
from semg_network import Network, Network_enhanced


class Trainer():
    def __init__(self,model,optimizer,criterion,device,scheduler=None,epochs=10):
        self.model = model
        self.optimizer = optimizer
        self.criterion = criterion
        self.scheduler = scheduler
        self.device = device
        self.max_epochs = epochs
        self.data = np.load("nina_data/all_6C_data_1.npy",allow_pickle='TRUE').item()
        self.train_data_len = len(self.data['train'])
        self.test_data_len = len(self.data['eval'])
        self.stats = {'loss': float('+inf'),
                           'model_wt': copy.deepcopy(self.model.state_dict()),
                           'acc': 0,
                           'epoch': 0}
        # self.best_model_wts = copy.deepcopy(self.model.state_dict())


    def one_epoch(self,phase):
        running_loss = 0.0
        cor_classify = 0.0
        i = 0
        for input,label in self.data[phase]:
            if phase == 'train':
                self.model.train()
                torch.set_grad_enabled(True)
                self.optimizer.zero_grad()
            elif phase == 'eval':
                self.model.eval()
                torch.set_grad_enabled(False)

            input = torch.from_numpy(input)
            label = torch.from_numpy(np.array([label]))
            input = input.view(1,1,input.shape[0],input.shape[1])
            input = input.to(self.device)
            label = label.to(self.device)

            output = self.model(input)
            loss = self.criterion(output,label.float())
            running_loss += loss.item()

            if phase == 'train':
                loss.backward()
                # try:
                #     loss.backward()
                # except:
                #     print("{}  loss: {:.8f}".format(i,loss))
                self.optimizer.step()

            #Does prediction == actual class?
            cor_classify += (torch.argmax(output,dim=1) == torch.argmax(label)).sum().item()
            i+=1

        return running_loss, cor_classify


    def train(self,val_train=True):
        since = time.time()
        # self.model.train()
        # torch.set_grad_enabled(True)

        prev_loss = 0
        loss_cnt = 0
        print('Training...\n')
        for epoch in range(1,self.max_epochs+1):
            e_loss, e_classify = self.one_epoch('train')
            e_acc = (e_classify/self.train_data_len)*100
            print("Epoch: {}/{}\nPhase: Train  Loss: {:.8f}    Accuracy: {:.4f}".format(epoch,self.max_epochs,e_loss,e_acc))
            if val_train:
                t_loss, t_acc = self.test(False,epoch)
                print("Phase: Validation    Loss: {:.8f}    Accuracy: {:.4f}".format(t_loss,t_acc))
            elif e_loss < self.stats['loss']:
                self.stats = {'loss': e_loss,
                                   'model_wt': copy.deepcopy(self.model.state_dict()),
                                   'acc': e_acc,
                                   'epoch': epoch}

            '''Add early stopping: if change in loss less than ... x times, stop.
            Useful check if updating properly as well'''
            if (e_loss - prev_loss) < 1e-3: loss_cnt += 1
            if loss_cnt > 2: break
            prev_loss = e_loss

            if self.scheduler != None:
                self.scheduler.step()

        print("Training Summary:")
        print("Best epoch was {} of {} with Loss: {:.8f}    Accuracy: {:.4f}".format(self.stats['epoch'],epoch,self.stats['loss'],self.stats['acc']))
        total_time = time.time() - since
        print('Training completed in {:.0f}m {:.0f}s'.format(total_time//60,total_time%60))

    def test(self,use_best_wt,epoch):
        if use_best_wt:
            print("Testing with best weights...")
            self.model.load_state_dict(self.stats['model_wt'])

        test_loss, test_correct = self.one_epoch('eval')
        test_acc = (test_correct/self.test_data_len)*100
        if test_loss < self.stats['loss'] and not use_best_wt:
            self.stats = {'loss': test_loss,
                               'model_wt': copy.deepcopy(self.model.state_dict()),
                               'acc': test_acc,
                               'epoch': epoch}
        if use_best_wt:
            print("Test Summary:")
            print("    Loss = {:.8f}".format(test_loss))
            print("    Correct: {}/{}".format(test_correct,self.test_data_len))
            print("    Accuracy: {:.4f}".format(test_acc))
        return test_loss, test_acc


def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    ## Initialize model
    # model = Network(6)
    model = Network_enhanced(6)

    ## Initialize hyperparameters and supporting functions
    learning_rate = 0.002
    optimizer = optim.SGD(model.parameters(),lr=learning_rate)
    criterion = nn.MSELoss(reduction='mean')
    scheduler = lr_scheduler.StepLR(optimizer,step_size=10,gamma=0.1)
    ## Initialize network trainer class
    nt = Trainer(model,optimizer,criterion,device)

    ## Train and test network
    nt.train(val_train=True)
    tl, ta = nt.test(use_best_wt=True,1)


if __name__ == '__main__':
    main()
