ARG PORT=443
FROM cypress/browsers:latest
RUN apt-get install python3 -y
RUN echo $(python3 -m site --user_base)
COPY req.txt .
ENV PATH /home/root/.local/bin:${PATH}
RUN apt-get update && apt-get install -y python3-pip && pip install -r req.txt --break-system-packages
COPY . .
CMD python3 main.py
