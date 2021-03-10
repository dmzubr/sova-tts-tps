from tps.handler import Handler
from tps.utils import cleaners

if __name__ == '__main__':
    config_path = 'data/text_handler_natasha.yaml'
    handler = Handler.from_config(config_path)

    in_txt = 'на шлеме, которое затягивается, сломали в хлам..'
    print(in_txt)
    # res = handler.text2vec(in_txt)

    res = handler.generate(
        text=in_txt,
        cleaner=cleaners.light_punctuation_cleaners,
        # user_dict=self.user_dict,
        keep_delimiters=True,
        mask_stress=False,
        mask_phonemes=False
    )

    r = list(res)
    print(r)

    vec = handler.text2vec(r[0])
    print(vec)

    pass