
# ##  er模型


import warnings
warnings.filterwarnings('ignore')
import sys
sys.path.append('./codes')
import os
import argparse
import torch
import shutil

from models import GPERModel
from trainer import GPERTrainer
from data import GPERDataset, GPERDataProcessor
from utils import init_logger, seed_everything, get_devices, get_time

import torch.utils.data as Data
from torch import nn
from d2l import torch as d2l
from transformers import BertTokenizerFast, BertModel, AutoTokenizer, AutoModelForMaskedLM
MODEL_CLASS = {
    'bert': (BertTokenizerFast, BertModel),
    'roberta': (AutoTokenizer, AutoModelForMaskedLM),
    'mcbert': (AutoTokenizer, AutoModelForMaskedLM),
}


def get_args():
    parser = argparse.ArgumentParser()
    
    # 方法名：baseline required=True
    parser.add_argument("--method_name", default='gper', type=str,
                        help="The name of method.")
    
    # 数据集存放位置：./CMeIE required=True
    parser.add_argument("--data_dir", default='./CMeIE', type=str,
                        help="The task data directory.")
    
    parser.add_argument("--train_file", default='CMeIE_train.json', type=str,
                    help="The train file.")
    
    parser.add_argument("--dev_file", default='CMeIE_dev.json', type=str,
                        help="The dev file.")
    
    parser.add_argument("--test_file", default='CMeIE_test.json', type=str,
                        help="The test file.")
    
    # 预训练模型存放位置: ../../pretrained_model required=True
    parser.add_argument("--model_dir", default='/root/nas/Models', type=str,
                        help="The directory of pretrained models")
    
    # 模型类型: bert required=True
    parser.add_argument("--model_type", default='bert', type=str, 
                        help="The type of selected pretrained models.")
    
    # 预训练模型: bert-base-chinese required=True
    parser.add_argument("--pretrained_model_name", default='RoBERTa_zh_Large_PyTorch', type=str,
                        help="The path or name of selected pretrained models.")
    
    # 微调模型: er required=True
    parser.add_argument("--finetuned_model_name", default='gper', type=str,
                        help="The name of finetuned model")
    
    # 微调模型参数存放位置：./checkpoint required=True
    parser.add_argument("--output_dir", default='./checkpoint', type=str,
                        help="The path of result data and models to be saved.")
    
    # 是否训练：True
    parser.add_argument("--do_train", action="store_true",
                        help="Whether to run training.")
    
    # 是否预测：False required=True
    parser.add_argument("--do_predict", action="store_true",
                        help="Whether to run the models in inference mode on the test set.")
    
    # 预测时加载的模型版本，如果做预测，该参数是必需的
    parser.add_argument("--model_version", default='', type=str,
                        help="model's version when do predict")
    
    # 提交结果保存目录：./result_output required=True
    parser.add_argument("--result_output_dir", default='./result_output', type=str,
                        help="the directory of commit result to be saved")
    
    # 设备：-1：CPU， i：cuda:i(i>0), i可以取多个，以逗号分隔 required=True
    parser.add_argument("--devices", default='', type=str,
                        help="the directory of commit result to be saved")
    
    parser.add_argument("--loss_show_rate", default=200, type=int,
                        help="liminate loss to [0,1] where show on the train graph")
    
    # models param
    # 序列最大长度：128
    parser.add_argument("--max_length", default=256, type=int,
                        help="the max length of sentence.")
    
    # 训练batch_size：32
    parser.add_argument("--train_batch_size", default=24, type=int,
                        help="Batch size for training.")
    
    # 评估batch_size：64
    parser.add_argument("--eval_batch_size", default=512, type=int,
                        help="Batch size for evaluation.")
    
    # 学习率：3e-5
    parser.add_argument("--learning_rate", default=4e-5, type=float,
                        help="The initial learning rate for Adam.")
    
    # 权重衰退：取默认值
    parser.add_argument("--weight_decay", default=0.01, type=float,
                        help="Weight deay if we apply some.")
    
    # 极小值：取默认值
    parser.add_argument("--adam_epsilon", default=1e-8, type=float,
                        help="Epsilon for Adam optimizer.")
    
    # epochs：7
    parser.add_argument("--epochs", default=5, type=int,
                        help="Total number of training epochs to perform.")
    
    # 线性学习率比例：0.1
    parser.add_argument("--warmup_proportion", default=0.1, type=float,
                        help="Proportion of training to perform linear learning rate warmup for, "
                             "E.g., 0.1 = 10% of training.")
    
    # earlystop_patience：100 （earlystop_patience step 没有超过最高精度则停止训练）
    parser.add_argument("--earlystop_patience", default=100, type=int,
                        help="The patience of early stop")
    
    # 多少step后打印一次：200
    parser.add_argument('--logging_steps', type=int, default=200,
                        help="Log every X updates steps.")
    
    # 随机数种子：2021
    parser.add_argument('--seed', type=int, default=2021,
                        help="random seed for initialization")
    
    # 训练时保存 save_metric 最大存取模型 required=True
    parser.add_argument("--save_metric", default='step', type=str,
                        help="the metric determine which model to save.")
    
    # 是否做rdrop（变相的数据增强）
    parser.add_argument('--do_rdrop', action='store_true',
                        help="whether to do r-drop")
    
    parser.add_argument('--rdrop_type', type=str, default='softmax',
                        help="whether to do r-drop")
    
    # rdrop 中的参数，alpha越大则loss越偏向kl散度
    parser.add_argument('--rdrop_alpha', type=int, default=4,
                        help="hyper-parameter in rdrop")
    
    # 正则化手段，dropout
    parser.add_argument('--dropout', type=float, default=0.3,
                        help="dropout rate")

    # 最大梯度范数
    parser.add_argument('--max_grad_norm', type=float, default=1.0,
                        help="grad norm")
    
    # gplinker中的隐藏层维度
    parser.add_argument('--inner_dim', type=int, default=64,
                        help="inner dim of gplinker")

    parser.add_argument('--time', type=str, default='',
                        help="whether to use entity marker when sp2o")

    parser.add_argument('--predict_threshold', type=float, default=0.5,
                        help="p2so model's predict_threshold")

    # py版本
    args = parser.parse_args()

    args.devices = get_devices(args.devices.split(','))
    args.device = args.devices[0]

    seed_everything(args.seed)
    if args.time == '':
        args.time = get_time(fmt='%m-%d-%H-%M')
    
    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    args.output_dir = os.path.join(args.output_dir, args.method_name)
    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    args.output_dir = os.path.join(args.output_dir, args.pretrained_model_name)
    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    args.output_dir = os.path.join(args.output_dir, args.finetuned_model_name)
    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)
    print(args.output_dir)    
    args.result_output_dir = os.path.join(args.result_output_dir, args.finetuned_model_name) 
    if not os.path.exists(args.result_output_dir):
        os.mkdir(args.result_output_dir)
        
    if args.do_train:
        args.model_version = args.time
    if args.do_predict == True and args.model_version == '':
        raise Exception('做预测的话必须提供加载的模型版本')    
    return args


def main():
    args = get_args()
    tokenizer_class, model_class = MODEL_CLASS[args.model_type]
    additional_special_tokens = [f'[unused{i+1}]' for i in range(53)]
    if args.do_train:
        log_path = os.path.join(args.output_dir,args.time)
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        logger = init_logger(os.path.join(log_path, 'log.txt'))
        logger.info(f'Training {args.finetuned_model_name} model...')
        tokenizer = tokenizer_class.from_pretrained(os.path.join(args.model_dir, args.pretrained_model_name), do_lower_case=True)
        tokenizer.add_special_tokens({'additional_special_tokens': additional_special_tokens})
        
        data_processor = GPERDataProcessor(args)
        args.data_processor = data_processor
        train_samples = data_processor.get_train_sample()
        eval_samples = data_processor.get_dev_sample()
        merge_samples = data_processor.merge(train_samples,eval_samples)
        
        merge_samples =GPERDataset(merge_samples, data_processor, tokenizer=tokenizer, mode='train',
                                  max_length=args.max_length)

        model = GPERModel(model_class, args)
        print(model)
        trainer = GPERTrainer(args=args, model=model, data_processor=data_processor,
                            tokenizer=tokenizer, train_dataset=merge_samples, eval_dataset=None,
                            logger=logger)

        global_step, best_step = trainer.train()
        
        
    if args.do_predict:
        log_path = os.path.join(args.result_output_dir,args.data_dir,args.model_version)
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        logger = init_logger(os.path.join(log_path, 'log.txt'))
        load_dir = os.path.join(args.output_dir, args.model_version)
        logger.info(f'load tokenizer from {load_dir}')
        tokenizer = tokenizer_class.from_pretrained(load_dir)
        tokenizer.add_special_tokens({'additional_special_tokens': additional_special_tokens})
        
        data_processor = GPERDataProcessor(args)
        args.data_processor = data_processor
        test_samples = data_processor.get_test_sample()
        model = GPERModel(model_class, args)
        print(model)
        
        trainer = GPERTrainer(args=args, model=model, data_processor=data_processor,
                            tokenizer=tokenizer, logger=logger)
        trainer.load_checkpoint()
        trainer.predict()


if __name__ == '__main__':
    main()





