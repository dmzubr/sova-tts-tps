from typing import Union

from ...processor import Processor
from ....utils import load_dict, prob2bool
from ....ssymbols import punctuation, space, accent, shields
from ....types import Charset

"""
If you need to extend the Phonetizer functionality with
language-specific rules, just add a new descendant class.
"""

class Phonetizer(Processor):
    def __init__(self, charset: Union[Charset, str], dict_source: Union[str, tuple, list, dict]=None):
        """
        Base phonetizer with common functionality for all languages.

        :param dict_source: Union[str, tuple, list, dict]
            Source of dictionary that contains phonetization pairs such as (hello, HH AH L OW) in the case of CMU dict.
            Options:
                * str - path to file.
                    The file extension must explicitly show its format in case of json and yaml files.
                    In other cases, user must set the format himself (see below).
                * tuple, list - (path, format)
                    path - path to the dictionary file
                    format - format of the dictionary file (see tps.utils.load_dict function)
                * dict - just a dict
        """
        super().__init__(charset)

        fmt = None
        if isinstance(dict_source, (tuple, list)):
            dict_source, fmt = dict_source

        self.entries = load_dict(dict_source, fmt)


    def apply(self, string: str, **kwargs) -> str:
        """
        Splits passed string to tokens and convert each to stressed one if it presents in dictionary.
        Keep it mind, that tokenization is simple here and it's better to pass normalized string.

        :param string: str
            Your text.
        :param kwargs:
            * mask_phonemes: Union[bool, float]
                Whether to mask each token.
                If float, then masking probability will be computed for each token independently.
        :return: str
        """
        mask = kwargs.get("mask_phonemes", False)

        tokens = self.split_to_tokens(string, self._punct_re)

        for idx, token in enumerate(tokens):
            if token in punctuation + space:
                continue
            token = self._apply_to_token(token, mask)
            tokens[idx] = token

        return self.join_tokens(tokens)


    def _apply_to_token(self, token, mask):
        if prob2bool(mask):
            return token

        stress_exists = token.find(accent) != -1
        if not stress_exists: # we won't phonetize words without stress, that's all
            return token

        phoneme_token = self.entries.get(token, None)  # word -> W_O_R_D (if exists)
        token = shields[0] + phoneme_token + shields[1] if phoneme_token is not None else token  # W_O_R_D -> {W_O_R_D}

        return token