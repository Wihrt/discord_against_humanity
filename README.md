# Discord Against Humanity

## Purpose of the bot

It's a Discord Bot providing Cards Against Humanity

## How to use it

Just add it to your Discord server by using this link :
https://discordapp.com/api/oauth2/authorize?client_id=410847498417209354&permissions=268445696&scope=bot

## How to play

* Create your game by using `$create`
* Join your game by using `$join`
* Start your game by using `$start`


## Next steps

* ~~Adding more logging~~
* ~~Adding more documentation~~
* See how to manage players who join/leave the game during the game
* Supports localization


## Local install

* Clone this repository
* Put your token in /bot/token.txt
* Grab a JSON file from http://www.crhallberg.com/cah/ and put it in /ext/cah.json
* Run /ext/convert_cah.py
* Run `docker-compose build`
* Run `docker-compose run`


