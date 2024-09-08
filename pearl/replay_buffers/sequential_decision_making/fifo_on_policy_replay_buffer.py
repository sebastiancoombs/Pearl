# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
#

# pyre-strict

from typing import Optional

import torch

from pearl.api.action import Action
from pearl.api.action_space import ActionSpace
from pearl.api.reward import Reward
from pearl.api.state import SubjectiveState
from pearl.replay_buffers.tensor_based_replay_buffer import TensorBasedReplayBuffer
from pearl.replay_buffers.transition import Transition


class FIFOOnPolicyReplayBuffer(TensorBasedReplayBuffer):
    def __init__(self, capacity: int) -> None:
        super(FIFOOnPolicyReplayBuffer, self).__init__(capacity)
        # this is used to delay push SARS
        # wait for next action is available and then final push
        # this is designed for single transition for now
        self.cache: Optional[Transition] = None

    def push(
        self,
        state: SubjectiveState,
        action: Action,
        reward: Reward,
        terminated: bool,
        curr_available_actions: Optional[ActionSpace] = None,
        next_state: Optional[SubjectiveState] = None,
        next_available_actions: Optional[ActionSpace] = None,
        max_number_actions: Optional[int] = None,
        cost: Optional[float] = None,
    ) -> None:
        if curr_available_actions is None:
            raise ValueError(
                f"{type(self)} requires curr_available_actions not to be None"
            )

        if next_available_actions is None:
            raise ValueError(
                f"{type(self)} requires next_available_actions not to be None"
            )

        if next_state is None:
            raise ValueError(f"{type(self)} requires next_state not to be None")

        (
            curr_available_actions_tensor_with_padding,
            curr_unavailable_actions_mask,
        ) = self._create_action_tensor_and_mask(
            max_number_actions, curr_available_actions
        )

        (
            next_available_actions_tensor_with_padding,
            next_unavailable_actions_mask,
        ) = self._create_action_tensor_and_mask(
            max_number_actions, next_available_actions
        )

        current_state = self._process_single_state(state)
        current_action = self._process_single_action(action)

        if self.cache is not None:
            assert self.cache.next_state is not None
            find_match = torch.equal(self.cache.next_state, current_state)
        else:
            find_match = False

        if find_match:
            # push a complete SARSA into memory
            assert self.cache is not None
            self.memory.append(
                Transition(
                    state=self.cache.state,
                    action=self.cache.action,
                    reward=self.cache.reward,
                    next_state=self.cache.next_state,
                    next_action=current_action,
                    curr_available_actions=self.cache.curr_available_actions,
                    curr_unavailable_actions_mask=self.cache.curr_unavailable_actions_mask,
                    next_available_actions=self.cache.next_available_actions,
                    next_unavailable_actions_mask=self.cache.next_unavailable_actions_mask,
                    terminated=self.cache.terminated,
                )
            )
        if not terminated:
            # save current push into cache
            self.cache = Transition(
                state=current_state,
                action=current_action,
                reward=self._process_single_reward(reward),
                next_state=self._process_single_state(next_state),
                curr_available_actions=curr_available_actions_tensor_with_padding,
                curr_unavailable_actions_mask=curr_unavailable_actions_mask,
                next_available_actions=next_available_actions_tensor_with_padding,
                next_unavailable_actions_mask=next_unavailable_actions_mask,
                terminated=self._process_single_terminated(terminated),
            )
        else:
            # for terminal state, push directly
            self.memory.append(
                Transition(
                    state=current_state,
                    action=current_action,
                    reward=self._process_single_reward(reward),
                    next_state=self._process_single_state(next_state),
                    # this value doesnt matter, use current_action for same shape
                    next_action=current_action,
                    curr_available_actions=curr_available_actions_tensor_with_padding,
                    curr_unavailable_actions_mask=curr_unavailable_actions_mask,
                    next_available_actions=next_available_actions_tensor_with_padding,
                    next_unavailable_actions_mask=next_unavailable_actions_mask,
                    terminated=self._process_single_terminated(terminated),
                )
            )
