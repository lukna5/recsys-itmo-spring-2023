cd ..
cd botify
docker-compose stop
docker-compose up -d --build
cd ..
cd sim
python sim/run.py --episodes 1000 --config config/env.yml multi --processes 4