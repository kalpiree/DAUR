import numpy as np
import scipy.sparse as sp

class Interactions(object):
    def __init__(self, file_path,
                 user_map=None,
                 item_map=None):

        if not user_map and not item_map:
            user_map = dict()
            item_map = dict()

            num_user = 0
            num_item = 0
        else:
            num_user = len(user_map)
            num_item = len(item_map)

        user_ids = list()
        item_ids = list()

        with open(file_path, 'r') as fin:
            for line in fin:
                parts = line.strip().split()
                if len(parts) < 2:
                    print(f"Skipping malformed line: {line}")
                    continue
                u, i = parts[0], parts[1]
                user_ids.append(u)
                item_ids.append(i)

        for u in user_ids:
            if u not in user_map:
                user_map[u] = num_user
                num_user += 1
        for i in item_ids:
            if i not in item_map:
                item_map[i] = num_item
                num_item += 1

        user_ids = np.array([user_map[u] for u in user_ids])
        item_ids = np.array([item_map[i] for i in item_ids])

        self.num_users = num_user
        self.num_items = num_item

        self.user_ids = user_ids
        self.item_ids = item_ids

        self.user_map = user_map
        self.item_map = item_map

        self.sequences = None
        self.test_sequences = None

        self._sequence_encoded = False

    def __len__(self):
        return len(self.user_ids)

    def tocoo(self):
        row = self.user_ids
        col = self.item_ids
        data = np.ones(len(self))

        return sp.coo_matrix((data, (row, col)),
                             shape=(self.num_users, self.num_items))

    def tocsr(self):
        return self.tocoo().tocsr()

    def to_sequence(self, sequence_length=5, target_length=1):
        if not self._sequence_encoded:
            for k, v in self.item_map.items():
                self.item_map[k] = v + 1
            self.item_ids = self.item_ids + 1
            self.num_items += 1
            self._sequence_encoded = True

        max_sequence_length = sequence_length + target_length

        sort_indices = np.lexsort((self.user_ids,))
        user_ids = self.user_ids[sort_indices]
        item_ids = self.item_ids[sort_indices]

        user_ids, indices, counts = np.unique(user_ids,
                                              return_index=True,
                                              return_counts=True)

        num_subsequences = sum([c - max_sequence_length + 1 if c >= max_sequence_length else 1 for c in counts])

        sequences = np.zeros((num_subsequences, sequence_length), dtype=np.int64)
        sequences_targets = np.zeros((num_subsequences, target_length), dtype=np.int64)
        sequence_users = np.empty(num_subsequences, dtype=np.int64)

        test_sequences = np.zeros((self.num_users, sequence_length), dtype=np.int64)
        test_users = np.empty(self.num_users, dtype=np.int64)

        _uid = None
        for i, (uid, item_seq) in enumerate(_generate_sequences(user_ids, item_ids, indices, max_sequence_length)):
            if uid != _uid:
                test_sequences[uid][:] = item_seq[-sequence_length:]
                test_users[uid] = uid
                _uid = uid
            sequences_targets[i][:] = item_seq[-target_length:]
            sequences[i][:] = item_seq[:sequence_length]
            sequence_users[i] = uid

        self.sequences = SequenceInteractions(sequence_users, sequences, sequences_targets)
        self.test_sequences = SequenceInteractions(test_users, test_sequences)

class SequenceInteractions(object):
    def __init__(self, user_ids, sequences, targets=None):
        self.user_ids = user_ids
        self.sequences = sequences
        self.targets = targets

        self.L = sequences.shape[1]
        self.T = targets.shape[1] if targets is not None else None

def _sliding_window(tensor, window_size, step_size=1):
    if len(tensor) - window_size >= 0:
        for i in range(len(tensor), 0, -step_size):
            if i - window_size >= 0:
                yield tensor[i - window_size:i]
            else:
                break
    else:
        num_paddings = window_size - len(tensor)
        yield np.pad(tensor, (num_paddings, 0), 'constant')

def _generate_sequences(user_ids, item_ids, indices, max_sequence_length):
    for i in range(len(indices)):
        start_idx = indices[i]
        stop_idx = indices[i + 1] if i < len(indices) - 1 else None
        for seq in _sliding_window(item_ids[start_idx:stop_idx], max_sequence_length):
            yield (user_ids[i], seq)
