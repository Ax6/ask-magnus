 clean:
	docker stop ask-magnus-cache
	docker remove ask-magnus-cache

init-cache:
	docker run --name ask-magnus-cache -v $(shell pwd)/data/redis:/data -p 6379:6379 -d redis redis-server --save 60 1 --loglevel warning

