import tensorflow as tf
from darknet53_trainable import Darknet53
from yolo_layer import yolo_head, yolo_det, preprocess_true_boxes, confidence_loss, cord_cls_loss
import config as cfg


class yolov3:

    def __init__(self, img, truth, istraining, decay_bn=0.99):
        self.img = img
        self.truth = truth
        self.istraining = istraining
        self.decay_bn = decay_bn
        self.img_shape = tf.shape(self.img)
        with tf.variable_scope("Feature_Extractor"):
            feature_extractor = Darknet53('darknet53.conv.74.npz', scratch=cfg.scratch)
            self.feats52 = feature_extractor.build(self.img, self.istraining, self.decay_bn)
        with tf.variable_scope("Head"):
            head = yolo_head(self.istraining)
            self.yolo123, self.yolo456, self.yolo789 = head.build(self.feats52,
                                                                  feature_extractor.res18,
                                                                  feature_extractor.res10)
        with tf.variable_scope("Detection_0"):
            self.anchors0 = tf.constant(cfg.anchors[cfg.mask[0]], dtype=tf.float32)
            det = yolo_det(self.anchors0,  self.img_shape)
            self.pred_xy0, self.pred_wh0, self.pred_confidence0, self.loc_txywh0 = det.build(self.yolo123)
        with tf.variable_scope("Detection_1"):
            self.anchors1 = tf.constant(cfg.anchors[cfg.mask[1]], dtype=tf.float32)
            det = yolo_det(self.anchors1,  self.img_shape)
            self.pred_xy1, self.pred_wh1, self.pred_confidence1, self.loc_txywh1 = det.build(self.yolo456)
        with tf.variable_scope("Detection_2"):
            self.anchors2 = tf.constant(cfg.anchors[cfg.mask[2]], dtype=tf.float32)
            det = yolo_det(self.anchors2,  self.img_shape)
            self.pred_xy2, self.pred_wh2, self.pred_confidence2, self.loc_txywh2 = det.build(self.yolo789)


    def compute_loss(self):
        with tf.name_scope('Loss_0'):
            matching_true_boxes, detectors_mask, loc_scale,iou_scores,idx,idx_i = preprocess_true_boxes(self.truth,
                                                                                   self.anchors0,
                                                                                   tf.shape(self.yolo123),
                                                                                   self.img_shape)
            objectness_loss_0,no_objects_loss_mean_0 = confidence_loss(self.pred_xy0, self.pred_wh0, self.pred_confidence0, self.truth, detectors_mask)
            coordinates_loss_sum_0,AVG_IOU_0 = cord_cls_loss(detectors_mask, matching_true_boxes,
                                        self.loc_txywh0, loc_scale)
            loss1 = objectness_loss_0 +coordinates_loss_sum_0+no_objects_loss_mean_0
        with tf.name_scope('Loss_1'):
            matching_true_boxes, detectors_mask, loc_scale,iou_scores,idx,idx_i = preprocess_true_boxes(self.truth,
                                                                                   self.anchors1,
                                                                                   tf.shape(self.yolo456),
                                                                                   self.img_shape)
            objectness_loss_1,no_objects_loss_mean_1 = confidence_loss(self.pred_xy1, self.pred_wh1, self.pred_confidence1, self.truth, detectors_mask)
            coordinates_loss_sum_1,AVG_IOU_1 = cord_cls_loss(detectors_mask, matching_true_boxes,
                                        self.loc_txywh1, loc_scale)
            loss2 = objectness_loss_1 +coordinates_loss_sum_1+no_objects_loss_mean_1
        with tf.name_scope('Loss_2'):
            matching_true_boxes, detectors_mask, loc_scale ,iou_scores,idx,idx_i= preprocess_true_boxes(self.truth,
                                                                                   self.anchors2,
                                                                                   tf.shape(self.yolo789),
                                                                                   self.img_shape)
            objectness_loss_2,no_objects_loss_mean_2 = confidence_loss(self.pred_xy2, self.pred_wh2, self.pred_confidence2, self.truth, detectors_mask)
            coordinates_loss_sum_2 ,AVG_IOU_2= cord_cls_loss(detectors_mask, matching_true_boxes,
                                        self.loc_txywh2, loc_scale)
            loss3 = objectness_loss_2 + coordinates_loss_sum_2+no_objects_loss_mean_2

        self.loss = (loss1 + loss2 + loss3)/3
        AVG_IOU=(AVG_IOU_0+AVG_IOU_1+AVG_IOU_2)/3      
        coordinates_loss=(coordinates_loss_sum_0+coordinates_loss_sum_1+coordinates_loss_sum_2)/3
        objectness_loss=(objectness_loss_0+objectness_loss_1+objectness_loss_2)/3
        no_objects_loss=(no_objects_loss_mean_0+no_objects_loss_mean_1+no_objects_loss_mean_2)/3
        return self.loss,AVG_IOU,coordinates_loss,objectness_loss,no_objects_loss,matching_true_boxes, detectors_mask, loc_scale,iou_scores,idx,idx_i

    def pedict(self, img_hw, iou_threshold=0.5, score_threshold=0.5):
        """
        follow yad2k - yolo_eval
        For now, only support single image prediction
        :param iou_threshold:
        :return:
        """
        img_hwhw = tf.expand_dims(tf.stack([img_hw[0], img_hw[1]] * 2, axis=0), axis=0)
        with tf.name_scope('Predict_0'):
            pred_loc0 = tf.concat([self.pred_xy0[..., 1:] - 0.5 * self.pred_wh0[..., 1:],
                                   self.pred_xy0[..., 0:1] - 0.5 * self.pred_wh0[..., 0:1],
                                   self.pred_xy0[..., 1:] + 0.5 * self.pred_wh0[..., 1:],
                                   self.pred_xy0[..., 0:1] + 0.5 * self.pred_wh0[..., 0:1]
                                   ], axis=-1)  # (y1, x1, y2, x2)
            pred_loc0 = tf.maximum(tf.minimum(pred_loc0, 1), 0)
            pred_loc0 = tf.reshape(pred_loc0, [-1, 4]) * img_hwhw
            pred_obj0 = tf.reshape(self.pred_confidence0, shape=[-1])
        with tf.name_scope('Predict_1'):
            pred_loc1 = tf.concat([self.pred_xy1[..., 1:] - 0.5 * self.pred_wh1[..., 1:],
                                   self.pred_xy1[..., 0:1] - 0.5 * self.pred_wh1[..., 0:1],
                                   self.pred_xy1[..., 1:] + 0.5 * self.pred_wh1[..., 1:],
                                   self.pred_xy1[..., 0:1] + 0.5 * self.pred_wh1[..., 0:1]
                                   ], axis=-1)  # (y1, x1, y2, x2)
            pred_loc1 = tf.maximum(tf.minimum(pred_loc1, 1), 0)
            pred_loc1 = tf.reshape(pred_loc1, [-1, 4]) * img_hwhw
            pred_obj1 = tf.reshape(self.pred_confidence1, shape=[-1])
        with tf.name_scope('Predict_2'):
            pred_loc2 = tf.concat([self.pred_xy2[..., 1:] - 0.5 * self.pred_wh2[..., 1:],
                                   self.pred_xy2[..., 0:1] - 0.5 * self.pred_wh2[..., 0:1],
                                   self.pred_xy2[..., 1:] + 0.5 * self.pred_wh2[..., 1:],
                                   self.pred_xy2[..., 0:1] + 0.5 * self.pred_wh2[..., 0:1]
                                   ], axis=-1)  # (y1, x1, y2, x2)
            pred_loc2 = tf.maximum(tf.minimum(pred_loc2, 1), 0)
            pred_loc2 = tf.reshape(pred_loc2, [-1, 4]) * img_hwhw
            pred_obj2 = tf.reshape(self.pred_confidence2, shape=[-1])

        self.pred_loc = tf.concat([pred_loc0, pred_loc1, pred_loc2], axis=0, name='pred_y1x1y2x2')
        self.pred_obj = tf.concat([pred_obj0, pred_obj1, pred_obj2], axis=0, name='pred_objectness')

        # score filter
        box_scores = tf.expand_dims(self.pred_obj, axis=1) 
        box_scores_max = tf.reduce_max(box_scores, axis=-1)     

        pred_mask = box_scores_max > score_threshold
        boxes = tf.boolean_mask(self.pred_loc, pred_mask)
        scores = tf.boolean_mask(box_scores_max, pred_mask)

        # non_max_suppression
        idx_nms = tf.image.non_max_suppression(boxes, scores,
                                               max_output_size=100,
                                               iou_threshold=iou_threshold)
        boxes = tf.gather(boxes, idx_nms)
        scores = tf.gather(scores, idx_nms)

        return boxes, scores






