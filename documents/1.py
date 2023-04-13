import os
import openai

openai.api_key = "1111"
ret = openai.Image.create(
  prompt="(((masterpiece))),best quality, illustration,(beautiful detailed girl),beautiful detailed glow,detailed ice,beautiful detailed water,(beautiful detailed eyes),expressionless,(floating palaces),azure hair,disheveled hair,long bangs, hairs between eyes,(skyblue dress),black ribbon,white bowties,midriff,{{{half closed eyes}}},big forhead,blank stare,flower,large top sleeves",
  n=2,
  size="1024x1024"
)

print(f'{ret}')