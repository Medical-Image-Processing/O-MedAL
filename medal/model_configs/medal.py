import numpy as np
import abc

from .. import checkpointing
from .baseline_inception import BaselineInceptionV3BinaryClassifier
from .baseline_squeezenet import BaselineSqueezeNetBinaryClassifier
from . import feedforward


def pick_initial_data_points_to_label(config):
    # TODO: how many?
    return np.random.randint(0, config.train_indices.size)


def pick_data_points_to_label(config):
    # define set of unlabeled points
    # get model prediction
    #  unlabeled_data_loader = feedforward.create_data_loader(
            #  config, idxs=config.train_indices[config.is_labeled])
    #  for embeddings in get_feature_embedding(config, unlabeled_data_loader)

    # set up model to extract feature
    return np.random.randint(0, config.train_indices.size)


def train(config):
    """Train a feedforward network using MedAL method"""

    for al_iter in range(config.cur_al_iter + 1, config.al_iters + 1):
        # update state for new al iteration
        config.cur_epoch = 0
        config.cur_al_iter = al_iter
        config.train_loader = feedforward.create_data_loader(
            config, idxs=config.train_indices[config.is_labeled])

        # train model the regular way
        feedforward.train(config)  # train for many epochs

        # pick unlabeled points to label
        mask = pick_data_points_to_label(config)
        assert mask.sum() > 0
        assert (config.is_labeled[mask] == 0).all()  # sanity check
        config.is_labeled[mask] = 1


class MedalConfigABC(feedforward.FeedForwardModelConfig):
    """Base class for all MedAL models"""
    run_id = str
    al_iters = int

    @abc.abstractmethod
    def get_feature_embedding(self, points):
        raise NotImplemented

    checkpoint_fname = \
        "{config.run_id}/al_{config.cur_al_iter}_epoch_{config.cur_epoch}.pth"
    cur_al_iter = 0  # it's actually 1 indexed

    def train(self):
        return train(self)

    def load_checkpoint(self, check_loaded_all_available_data=True):
        extra_state = super().load_checkpoint()
        # ensure loaded right checkpoint
        # same processing that feedforward does for epoch.
        if self.cur_al_iter != 0:
            checkpointing.ensure_consistent(
                extra_state, key='al_iter', value=self.cur_al_iter)
        elif extra_state is None:  # no checkpoint found
            return

        self.cur_al_iter = extra_state.pop('al_iter')
        if check_loaded_all_available_data:
            assert len(extra_state) == 0, extra_state
        return extra_state

    def __init__(self, config_override_dict):
        super().__init__(config_override_dict)

        # override the default feedforward config
        self.log_msg_minibatch = \
            "--> al_iter {config.cur_al_iter} " + self.log_msg_minibatch[4:]
        self.log_msg_epoch = \
            "al_iter {config.cur_al_iter} " + self.log_msg_epoch

        # split train set into unlabeled and labeled points
        self.train_indices = self.train_loader.sampler.indices.copy()
        del self.train_loader  # will recreate appropriately during train.
        self.is_labeled = np.zeros_like(self.train_indices)

        mask = pick_initial_data_points_to_label(self)
        self.is_labeled[mask] = 1


class MedalInceptionV3BinaryClassifier(MedalConfigABC,
                                       BaselineInceptionV3BinaryClassifier):
    run_id = 'medal_inceptionv3'
    al_iters = 34

    def get_feature_embedding(self, points):
        raise NotImplemented


class MedalSqueezeNetBinaryClassifier(MedalConfigABC,
                                      BaselineSqueezeNetBinaryClassifier):
    run_id = 'medal_squeezenet'
    al_iters = 34

    def get_feature_embedding(self, points):
        raise NotImplemented