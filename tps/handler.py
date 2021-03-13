import re
from typing import Union, Callable, Iterator

from ..tps import ssymbols as smb
from .utils.cleaners import invalid_charset_cleaner, collapse_whitespace
from .utils import load_dict
from ..tps import modules as md
from .types import Charset, Delimiter, Module, BasedOn


_curly = re.compile("({}.+?{})".format(*smb.shields))
_invalid_symbols_dict = {
    Charset.en: smb.symbols_en + smb.shields + [smb.separator],
    Charset.en_cmu: smb.symbols_en_cmu + smb.shields + [smb.separator],
    Charset.ru: smb.symbols_ru + smb.shields + [smb.separator],
    Charset.ru_trans: smb.symbols_ + smb.GRAPHEMES_RU + smb.PHONEMES_RU_TRANS + smb.shields + [smb.separator],
}


class Handler(md.Processor):
    def __init__(self, charset: str, modules: list, out_max_length: int=None):
        super().__init__(charset)
        self.symbols = smb.symbols_dict[charset]

        # Mappings from symbol to numeric ID and vice versa:
        self.symbol_to_id = {s: i for i, s in enumerate(self.symbols)}
        self.id_to_symbol = {i: s for i, s in enumerate(self.symbols)}

        self.modules = modules
        self._preprocessor_dict = None
        self._validate_modules()

        self.out_max_length = out_max_length

        self._out_data = {}
        self._invalid_charset = re.compile(
            "[^{}]".format(
                "".join(sorted(_invalid_symbols_dict[self.charset]))
            )
        )


    def __call__(self, text: str, cleaner: Callable[[str], str]=None, user_dict: dict=None, keep_delimiters: bool=True,
                 **kwargs) -> list:
        units = list(self.generate(text, cleaner, user_dict, keep_delimiters, **kwargs))
        return units


    def generate(self, text: str, cleaner: Callable[[str], str]=None, user_dict: dict=None, keep_delimiters: bool=True,
                 **kwargs) -> Iterator[Union[str, Delimiter]]:
        self._clear_state()
        kwargs["user_dict"] = user_dict

        text = cleaner(text) if cleaner is not None else text
        text = text.lower()

        sentences = self.split_to_sentences(text, keep_delimiters)
        self._out_data = {sentence: [] for sentence in sentences}

        for sentence in sentences:
            if not isinstance(sentence, Delimiter):
                sentence = self.apply_to_sentence(sentence, **kwargs)

                if self.out_max_length is not None:
                    _units = self.split_to_units(sentence, self.out_max_length, keep_delimiters)

                    for unit in _units:
                        yield unit
                else:
                    yield sentence
            elif keep_delimiters:
                yield sentence
            else:
                continue


    def apply(self, string: str, **kwargs) -> str:
        module: md.Processor
        user_dict = kwargs.pop("user_dict", None)

        origin_string = string

        if user_dict is not None:
            string = self.dict_check(string, user_dict)
            self._out_data[origin_string].append(string)

        for module in self.modules:
            string = module.apply_to_sentence(string, **kwargs)
            self._out_data[origin_string].append(string)

        string = invalid_charset_cleaner(string, self._invalid_charset)
        string = collapse_whitespace(string)  # need to clean multiple white spaces that have appeared

        return string


    def dict_check(self, string: str, user_dict: dict) -> str:
        words = self.split_to_words(string)

        regexp_case = []
        for i, word in enumerate(words):
            if word in user_dict:
                item = user_dict[word]

                if isinstance(item, dict):
                    regexp_case.append(word)
                else:
                    words[i] = item

        regexp_case = set(regexp_case)
        string = self.join_words(words)

        for word in regexp_case:
            for case, value in user_dict[word].items():
                regexp = re.compile(case)
                string = regexp.sub(lambda elem: value, string)

        return string


    def text2vec(self, string: str) -> list:
        string = _curly.split(string)
        vector = []
        for elem in string:
            if elem.startswith(smb.shields[0]):
                elem = elem[1:-1].split(smb.separator)
            else:
                elem = list(elem)

            vector.extend(elem)

        print(vector)
        return [self.symbol_to_id[s] for s in vector if self._should_keep_symbol(s)]


    def vec2text(self, vector: list) -> str:
        text = []
        word = []
        prev = None
        for elem_idx in vector:
            elem = self.id_to_symbol[elem_idx]
            if elem in smb.PHONEMES or (elem in [smb.hyphen, smb.accent] and prev in smb.PHONEMES):
                word.append(elem)
            else:
                if word:
                    text.append(smb.shields[0] + smb.separator.join(word) + smb.shields[1])
                text.append(elem)
                word = []
            prev = elem

        if word:
            text.append(smb.shields[0] + smb.separator.join(word) + smb.shields[1])

        return "".join(text)


    def check_eos(self, text: str):
        text = text if text.endswith(smb.eos) else text + smb.eos
        return text


    @classmethod
    def from_config(cls, config: Union[str, tuple, dict]):
        config = load_dict(config, "yaml")

        handler_config = config["handler"]

        out_max_length = handler_config["out_max_length"]
        modules_list = handler_config["modules"]
        charset = Charset(handler_config["charset"])

        modules = []
        for module in modules_list:
            module = Module(module)
            module_config = config[module.value]
            module_config["charset"] = charset

            modules.append(_get_module(module, module_config))

        return Handler(charset, modules, out_max_length)


    def _should_keep_symbol(self, s):
        return s in self.symbol_to_id


    def _validate_modules(self):
        emphasizer_exists = False
        phonetizer_type = None

        for i, module in enumerate(self.modules):
            if isinstance(module, md.Emphasizer):
                emphasizer_exists = True
            elif isinstance(module, md.Phonetizer):
                phonetizer_type = type(module)

                assert i + 1 == len(self.modules), "Phonetizer module must be the last one"
                if not emphasizer_exists:
                    print("There is no emphasizer in modules. "
                          "Phonetizer will process words only with stress tokens set by user")

        if self.charset == Charset.ru_trans:
            assert phonetizer_type == md.RUglyPhonetizer, \
                "Wrong phonetizer type {} for current charset {}".format(phonetizer_type, self.charset)
        # elif self.charset == types.Charset.en_cmu:
        #     assert phonetizer_type == md.EnPhonetizer


    def _clear_state(self):
        del self._out_data
        self._out_data = {}


def get_symbols_length(charset: str):
    charset = Charset[charset]
    return len(smb.symbols_dict[charset])


_modules_dict = {
    Module.emphasizer: {
        BasedOn.rule: {
            Charset.ru: {
                "module": md.Emphasizer,
                "args": ("charset", ),
                "optional": ("dict_source", "prefer_user")
            },
            Charset.ru_trans: Charset.ru
        }
    },
    Module.phonetizer: {
        BasedOn.rule: {
            Charset.ru_trans: {
                "module": md.RUglyPhonetizer,
                "optional": ("dict_source", )
            }
        }
    }
}


def _get_module(module_type, module_config):
    module_tree = _modules_dict[module_type]

    based_on = BasedOn(module_config["type"])

    if based_on not in module_tree:
        raise NotImplementedError
    else:
        language_tree = module_tree[based_on.value]
        charset = module_config["charset"]

        if charset not in language_tree:
            raise NotImplementedError
        else:
            config = language_tree[charset]

            if isinstance(config, Charset):
                config = language_tree[config]

    module = config["module"]
    arguments = {arg: module_config[arg] for arg in config.get("args", ())}
    assert all(arg is not None for arg in arguments.values())

    optional = {arg: module_config[arg] for arg in config.get("optional", {})}
    optional = {arg: value for arg, value in optional.items() if value is not None}
    # in case of None value there will be taken default value of a method for the optional arg

    arguments.update(optional)

    return module(**arguments)
