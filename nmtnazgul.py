#!/usr/bin/python3

# Builtin imports
import sock
import sys
import json
import yaml
from time import time

# 3rd party imports
from nltk import sent_tokenize
import configargparse

# Self defined imports
from translator import Translator
from constraints import getPolitenessConstraints as getCnstrs
from log import log


class NMT_Server:
    def __init__(self, translator_engine: Translator):
        self.engine = translator_engine

    def parse_input(self, raw_msg):
        try:
            fullText = raw_msg['src']
            raw_style, raw_out_lang = get_conf(raw_msg['conf'])

            livesubs = "|" in fullText

            sentences = fullText.split("|") if livesubs else sent_tokenize(fullText)
            delim = "|" if livesubs else " "

        except KeyError:
            sentences = raw_msg['sentences']
            raw_style = raw_msg['outStyle']
            raw_out_lang = raw_msg['outLang']
            delim = False

        if raw_out_lang not in supportedOutLangs:
            # raise ValueError("out lang bad: " + rawOutLang)
            raw_out_lang = defaultOutLang

        outputLang = raw_out_lang
        # outputStyle = styleToDomain[rawStyle]
        outputStyle = None

        return sentences, outputLang, outputStyle, delim

    def decode_request(self, raw_msg):
        struct = json.loads(raw_msg.decode('utf-8'))

        segments, output_lang, output_style, delim = self.parse_input(struct)

        return segments, output_lang, output_style, delim

    def encode_response(self, translation_list, delim):
        translation_text = delim.join(translation_list)

        # TODO: Check what to do with raw_trans and raw_input? Some legacy thing?
        result = json.dumps({'final_trans': translation_text})

        return bytes(result, 'utf-8')

    def translation_wrapper(self, raw_msg):
        segments, output_lang, output_style, delim = self.decode_request(raw_msg)

        # TODO: Handle multiple out_languages, until then, just multiply one...
        translations, _, _, _ = self.engine.translate(segments, [output_lang] * len(segments))

        return self.encode_response(translations, delim)

    def start_translation_server(self, ip, port):
        log("started server")

        # start listening as a socket server; apply serverTranslationFunc to incoming messages to generate the response
        sock.startServer(self, port=port, host=ip)


def get_conf(raw_conf):
    style = 'auto'
    outlang = 'en'

    for field in raw_conf.split(','):
        if field in supportedOutLangs:
            outlang = field

    return style, outlang





if __name__ == "__main__":
    parser = configargparse.ArgParser(
        description="Backend NMT server for Sockeye models. Further info: http://github.com/tartunlp/nazgul",
        config_file_parser_class=configargparse.YAMLConfigFileParser,
        default_config_files=["config/config.ini"]
    )
    parser.add_argument('--config', type=yaml.safe_load)
    parser.add_argument("--models", "-m", required=True, type=str, help="Path to Sockeye model folder")
    parser.add_argument("--spm_model", "-s", required=True, type=str,
                        help="Path to trained Google SentencePiece model file")
    parser.add_argument("--tc_model", "-t", type=str, default=None,
                        help="Path to trained TartuNLP truecaser model file")
    parser.add_argument("--cpu", default=False, action="store_true",
                        help="Use CPU-s instead of GPU-s for serving")

    parser.add_argument("--port", "-p", type=int, default=12345,
                        help="Port to run the service on.")
    parser.add_argument("--ip", "-i", type=str, default="127.0.0.1",
                        help="IP to run the service on")

    parser.add_argument("--langs", "-l", type=str, action="append",
                        help="Comma separated string on supported languages.")
    parser.add_argument("--domains", "-d", type=str, action="append",
                        help="Comma separated string on supported domains.")

    args = parser.parse_args()
    print(args)

    ### Legacy stuff
    # read translation and preprocessing model paths off cmdline
    # modelPaths = readCmdlineModels()

    # read output language and style off cmdline -- both are optional and will be "None" if not given
    # olang, ostyle = readLangAndStyle()
    supportedOutLangs = args.langs
    defaultOutLang = "et"
    # load translation and preprocessing models using paths
    translation_engine = Translator(args.models, args.spm_model, args.tc_model, args.cpu)

    nmt_server = NMT_Server(translation_engine)
    nmt_server.start_translation_server(args.ip, args.port)
