FROM python:3.10

WORKDIR /service

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir poetry \
&& poetry config virtualenvs.create false \
&& poetry install --no-dev \
&& pip uninstall --yes poetry

CMD python server.py
