FROM python:3.13-slim AS requirements-stage

WORKDIR /tmp

RUN pip install uv

COPY ./pyproject.toml ./uv.lock /tmp/

RUN uv export --format requirements.txt -o requirements.txt --no-dev


FROM python:3.13-slim

WORKDIR /code

COPY --from=requirements-stage /tmp/requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./src /code/app

COPY ./entrypoint.sh /entrypoint.sh

CMD ["sh", "/entrypoint.sh"]
