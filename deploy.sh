#!/bin/bash
cd backend
flyctl deploy
cd -
cd frontend
flyctl deploy 
cd -
