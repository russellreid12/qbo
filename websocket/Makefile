.PHONY:clean

all:WebsocketServer

WebsocketServer:WebsocketServer.c
	gcc -std=c11 -Wall -Wextra -D_DEFAULT_SOURCE WebsocketServer.c -o WebsocketServer -lwebsockets -lpthread

clean:
	-rm WebsocketServer
