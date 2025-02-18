import json
import logging
import uuid

import aiohttp
import discord
import discord.ext.commands as commands
from discord.ext.commands.errors import UserInputError

import bot.bot_secrets as bot_secrets
import bot.extensions as ext
from bot.consts import Colors
from bot.messaging.events import Events

log = logging.getLogger(__name__)

LANGUAGE_NAME_TO_SHORT_CODE = {
"Afrikaans":"af",      
"Albanian":"sq",      
"Amharic":"am",      
"Arabic":"ar",      
"Armenian":"hy",      
"Assamese":"as",      
"Azerbaijani":"az",      
"Bangla":"bn",      
"Bashkir":"ba",      
"Bosnian (Latin)":"bs",      
"Bulgarian":"bg",      
"Cantonese (Traditional)":"yue",        
"Catalan":"ca",      
"Chinese (Literary)":"lzh",        
"Chinese Simplified":"zh-Hans",          
"Chinese Traditional":"zh-Hant",          
"Croatian":"hr",      
"Czech":"cs",      
"Danish":"da",      
"Dari":"prs",        
"Divehi":"dv",      
"Dutch":"nl",      
"English":"en",      
"Estonian":"et",      
"Fijian":"fj",      
"Filipino":"fil",        
"Finnish":"fi",      
"French":"fr",      
"French (Canada)":"fr-ca",        
"Georgian":"ka",      
"German":"de",      
"Greek":"el",      
"Gujarati":"gu",      
"Haitian Creole":"ht",      
"Hebrew":"he",      
"Hindi":"hi",      
"Hmong Daw":"mww",        
"Hungarian":"hu",      
"Icelandic":"is",      
"Indonesian":"id",      
"Inuinnaqtun":"ikt",        
"Inuktitut":"iu",      
"Inuktitut (Latin)":"iu-Latn",          
"Irish":"ga",      
"Italian":"it",      
"Japanese":"ja",      
"Kannada":"kn",      
"Kazakh":"kk",      
"Khmer":"km",      
"Klingon":"tlh-Lat",          
"Klingon (plqaD)":"tlh-Piq",          
"Korean":"ko",      
"Kurdish (Central)  ":"ku",      
"Kurdish (Northern)":"kmr",        
"Kyrgyz":"ky",      
"Lao":"lo",      
"Latvian":"lv",      
"Lithuanian":"lt",      
"Macedonian":"mk",      
"Malagasy":"mg",      
"Malay ":"ms",      
"Malayalam":"ml",      
"Maltese":"mt",      
"Maori":"mi",      
"Marathi":"mr",      
"Mongolian (Cyrillic)":"mn-Cyrl",          
"Mongolian (Traditional)":"mn-Mong",          
"Myanmar":"my",      
"Nepali":"ne",      
"Norwegian":"nb",      
"Odia":"or",      
"Pashto":"ps",      
"Persian ":"fa",      
"Polish":"pl",      
"Portuguese (Brazil)":"pt",      
"Portuguese (Portugal)":"pt-pt",        
"Punjabi":"pa",      
"Queretaro Otomi":"otq",        
"Romanian":"ro",      
"Russian":"ru",      
"Samoan":"sm",      
"Serbian (Cyrillic)":"sr-Cyrl",          
"Serbian (Latin)":"sr-Latn",          
"Slovak":"sk",      
"Slovenian":"sl",      
"Spanish":"es",      
"Swahili":"sw",      
"Swedish":"sv",      
"Tahitian":"ty",      
"Tamil":"ta",      
"Tatar":"tt",      
"Telugu":"te",      
"Thai":"th",      
"Tibetan":"bo",      
"Tigrinya":"ti",      
"Tongan":"to",      
"Turkish":"tr",      
"Turkmen":"tk",      
"Ukrainian":"uk",      
"Upper Sorbian":"hsb",        
"Urdu":"ur",      
"Uyghur":"ug",      
"Uzbek (Latin)":"uz",      
"Vietnamese":"vi",      
"Welsh":"cy",      
"Yucatec Maya":"yua",                           
                         
}
CHUNK_SIZE = 15
LANGUAGE_SHORT_CODE_TO_NAME = {value: key for key, value in LANGUAGE_NAME_TO_SHORT_CODE.items()}

TRANSLATE_API_URL = "https://api.cognitive.microsofttranslator.com/translate"

TRACE_ID = str(uuid.uuid4())


class TranslateCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @ext.group(case_insensitive=True, invoke_without_command=True)
    @ext.long_help(
        'Allows you to translate words or sentences by either specifying both the input and output language with the text to translate, or just the output language and the text to translate. run \'translate languages\' to see available languages')
    @ext.short_help('Translates words or phrases between two languages')
    @ext.example(('translate en spanish Hello', 'translate german Hello', 'translate languages', 'translate Spanish German Como estas?'))
    async def translate(self, ctx, *input: str):
        if len(input) < 2:
            raise UserInputError("Incorrect Number of Arguments. Minimum of 2 arguments")

        if is_valid_lang_code(input[1]):
            await self.translate_given_lang(ctx, input)
        else:
            await self.translate_detect_lang(ctx, input)

    @translate.command()
    @ext.long_help('Shows all available languages to translate between')
    @ext.short_help('Shows available languages')
    @ext.example(('translate languages'))
    async def languages(self, ctx):
        await self.bot.messenger.publish(Events.on_set_pageable_text,
                                         embed_name='Languages',
                                         field_title='Here are the available languages:',
                                         pages=get_language_list(self),
                                         author=ctx.author,
                                         channel=ctx.channel)
        return

    async def translate_given_lang(self, ctx, input):
        input_lang = await get_lang_code(self, ctx, input[0])
        output_lang = await get_lang_code(self, ctx, input[1])

        if input_lang == None or output_lang == None:
            return

        text = ' '.join(input[2:])

        params = {
            'api-version': '3.0',
            'from': input_lang,
            'to': output_lang
        }

        body = [{
            'text': text
        }]

        headers = {
            'Ocp-Apim-Subscription-Key': bot_secrets.secrets.azure_translate_key,
            'Ocp-Apim-Subscription-Region': 'global',
            'Content-type': 'application/json',
            'X-ClientTraceId': TRACE_ID
        }

        async with aiohttp.ClientSession() as session:
            async with await session.post(url=TRANSLATE_API_URL, params=params, headers=headers, json=body) as resp:
                response = json.loads(await resp.text())

        log.info(response[0]['translations'])
        embed = discord.Embed(title='Translate', color=Colors.ClemsonOrange)
        name = 'Translated to ' + LANGUAGE_SHORT_CODE_TO_NAME[response[0]['translations'][0]['to'].lower()]
        embed.add_field(name=name, value=response[0]['translations'][0]['text'], inline=False)
        await ctx.send(embed=embed)

    async def translate_detect_lang(self, ctx, input):
        output_lang = await get_lang_code(self, ctx, input[0])
        if output_lang == None:
            return

        text = ' '.join(input[1:])

        output_lang = await get_lang_code(self, ctx, output_lang)
        log.info(f'Output Lang Code: {output_lang}')

        params = {
            'api-version': '3.0',
            'to': output_lang
        }

        body = [{
            'text': text
        }]

        headers = {
            'Ocp-Apim-Subscription-Key': bot_secrets.secrets.azure_translate_key,
            'Ocp-Apim-Subscription-Region': 'global',
            'Content-type': 'application/json',
            'X-ClientTraceId': TRACE_ID
        }

        async with aiohttp.ClientSession() as session:
            async with await session.post(url=TRANSLATE_API_URL, params=params, headers=headers, json=body) as resp:
                response = json.loads(await resp.text())

        embed = discord.Embed(title='Translate', color=Colors.ClemsonOrange)
        name = 'Translated to ' + LANGUAGE_SHORT_CODE_TO_NAME[response[0]['translations'][0]['to'].lower()]
        embed.add_field(name=name, value=response[0]['translations'][0]['text'], inline=False)
        embed.add_field(name='Confidence Level:', value=response[0]['detectedLanguage']['score'], inline=True)
        embed.add_field(name='Detected Language:', value=LANGUAGE_SHORT_CODE_TO_NAME[response[0]['detectedLanguage']['language']], inline=True)
        await ctx.send(embed=embed)
        return


def is_valid_lang_code(input: str):
    return input.lower() in LANGUAGE_SHORT_CODE_TO_NAME or input.lower() in LANGUAGE_NAME_TO_SHORT_CODE


async def get_lang_code(self, ctx, input: str):
    if input.lower() in LANGUAGE_SHORT_CODE_TO_NAME:
        return input.lower()
    else:
        try:
            return LANGUAGE_NAME_TO_SHORT_CODE[input.lower()]
        except KeyError:
            pages = get_language_list(self)
            await self.bot.messenger.publish(Events.on_set_pageable_text,
                                             embed_name='Languages',
                                             field_title='Given language \'' + input + '\' not valid. Here are the available languages:',
                                             pages=pages,
                                             author=ctx.author,
                                             channel=ctx.channel)


def get_language_list(self):
    langs = [f'{name} ({short})' for name, short in LANGUAGE_NAME_TO_SHORT_CODE.items()]
    return ['\n'.join(i) for i in chunk_list(self, langs, CHUNK_SIZE)]


def chunk_list(self, lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def setup(bot):
    bot.add_cog(TranslateCog(bot))
